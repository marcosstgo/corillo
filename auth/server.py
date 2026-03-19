"""
corillo-auth — servicio minimalista de autenticación RTMP para MediaMTX.
Solo hace una cosa: validar stream keys contra PocketBase.
Puerto 3002. Sin dependencias del bot de chat.
"""
import os, time
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
        return cached["stream_key"] == secret
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
        return sk == secret
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

    # API interna — solo localhost
    if action in ("api", "metrics", "pprof"):
        if ip in ("127.0.0.1", "::1"):
            return Response(status_code=200)
        return Response(status_code=401)

    # Publish — validar stream key
    if action == "publish":
        params  = parse_qs(query.lstrip("?"))
        secret  = (params.get("secret") or params.get("pass") or [None])[0]
        if not secret:
            return Response(status_code=401)
        channel = path.removeprefix("live/").split("?")[0]
        valid   = await _validate(channel, secret)
        return Response(status_code=200 if valid else 401)

    return Response(status_code=401)


@app.get("/health")
def health():
    return {"status": "ok"}
