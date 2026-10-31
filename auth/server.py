"""
corillo-auth — servicio minimalista de autenticación RTMP para MediaMTX.
Solo hace una cosa: validar stream keys contra PocketBase.
Puerto 3002. Sin dependencias del bot de chat.
"""
import hmac, os, re, time
from urllib.parse import parse_qs
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import Response

load_dotenv()

PB_URL         = os.environ.get("PB_URL", "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS", "")

app = FastAPI()

_http: httpx.AsyncClient = None

_pb_token: dict = {"token": "", "ts": 0.0}
PB_TOKEN_TTL = 86400  # 24h

_key_cache: dict = {}  # canal → {"stream_key": str, "ts": float}
KEY_CACHE_TTL = 60     # segundos

CANAL_RE   = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")   # nombre de canal válido (y seguro para el filtro de PocketBase)
INTERNA_RE = re.compile(r"^live/[a-z0-9_-]+_(low|rtc)$")  # variantes que genera el propio server (720p y WebRTC)
LOCAL      = ("127.0.0.1", "::1")


@app.on_event("startup")
async def startup():
    global _http
    _http = httpx.AsyncClient(timeout=5.0)


@app.on_event("shutdown")
async def shutdown():
    await _http.aclose()


async def _admin_token() -> str:
    now = time.time()
    if _pb_token["token"] and now - _pb_token["ts"] < PB_TOKEN_TTL:
        return _pb_token["token"]
    r = await _http.post(
        f"{PB_URL}/api/collections/_superusers/auth-with-password",
        json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
    )
    token = r.json()["token"]
    _pb_token.update({"token": token, "ts": now})
    return token


async def _validate(channel: str, secret: str) -> bool:
    now = time.time()
    cached = _key_cache.get(channel)
    if cached and now - cached["ts"] < KEY_CACHE_TTL:
        return hmac.compare_digest(cached["stream_key"], secret)
    try:
        token = await _admin_token()
        r = await _http.get(
            f"{PB_URL}/api/collections/streamers/records",
            headers={"Authorization": token},
            params={"filter": f'key="{channel}" && active=true', "fields": "key,stream_key"},
        )
        items = r.json().get("items", [])
        if not items:
            return False
        sk = items[0].get("stream_key", "")
        _key_cache[channel] = {"stream_key": sk, "ts": now}
        return bool(sk) and hmac.compare_digest(sk, secret)
    except Exception:
        return False


@app.post("/auth")
async def mtx_auth(request: Request):
    try:
        data = await request.json()
    except Exception:
        return Response(status_code=401)

    action = data.get("action", "")
    path   = data.get("path", "")
    ip     = data.get("ip", "")
    query  = data.get("query", "")

    # Viewers — libre
    if action in ("read", "playback"):
        return Response(status_code=200)

    # API interna — solo localhost y corillo-vps por el túnel WireGuard (10.77.0.1)
    if action in ("api", "metrics", "pprof"):
        if ip in ("127.0.0.1", "::1", "10.77.0.1"):
            return Response(status_code=200)
        return Response(status_code=401)

    # Publish de las variantes _low/_rtc: solo los ffmpeg del propio corillo-server (31-oct-2026).
    # Antes mediamtx las excluía de la auth y cualquiera en internet podía publicar ahí y reemplazar
    # el 720p o el WebRTC de un canal (overridePublisher: yes).
    if action == "publish" and INTERNA_RE.match(path):
        return Response(status_code=200 if ip in LOCAL else 401)

    # Publish — validar stream key
    if action == "publish":
        params  = parse_qs(query.lstrip("?"))
        secret  = (params.get("secret") or params.get("pass") or [None])[0]
        if not secret:
            return Response(status_code=401)
        channel = path.removeprefix("live/").split("?")[0]
        if not CANAL_RE.match(channel):
            return Response(status_code=401)
        valid   = await _validate(channel, secret)
        return Response(status_code=200 if valid else 401)

    return Response(status_code=401)


@app.get("/health")
def health():
    return {"status": "ok"}
