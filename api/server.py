"""
corillo-api — API pública de streamers: perfiles y regeneración de stream key.
Puerto 3004. Sin dependencias del chat ni de Telegram.
"""
import os, time, secrets
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

PB_URL         = os.environ.get("PB_URL", "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS", "")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://corillo.live", "http://localhost:8080"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_http: httpx.AsyncClient = None

_pb_token: dict = {"token": "", "ts": 0.0}
PB_TOKEN_TTL = 86400


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


@app.get("/profile/{key}")
async def get_profile(key: str):
    if not PB_ADMIN_EMAIL or not PB_ADMIN_PASS:
        raise HTTPException(status_code=404)
    try:
        token = await _admin_token()
        r = await _http.get(
            f"{PB_URL}/api/collections/streamers/records",
            headers={"Authorization": token},
            params={
                "filter": f'key="{key}" && active=true',
                "fields": "id,key,display_name,bio,color,twitch,instagram,tiktok,avatar,panels",
            },
        )
        items = r.json().get("items", [])
        if not items:
            raise HTTPException(status_code=404)
        rec = items[0]
        if rec.get("avatar"):
            rec["avatar_url"] = f"{PB_URL}/api/files/streamers/{rec['id']}/{rec['avatar']}"
        return rec
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404)


@app.post("/regen-stream-key")
async def regen_stream_key(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401)
    try:
        data = await request.json()
        record_id = data.get("record_id", "")
        if not record_id:
            raise HTTPException(status_code=400)
        r = await _http.get(
            f"{PB_URL}/api/collections/streamers/records/{record_id}",
            headers={"Authorization": auth_header},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=401)
        new_key = secrets.token_urlsafe(24)
        admin_token = await _admin_token()
        r2 = await _http.patch(
            f"{PB_URL}/api/collections/streamers/records/{record_id}",
            headers={"Authorization": admin_token},
            json={"stream_key": new_key},
        )
        if r2.status_code != 200:
            raise HTTPException(status_code=500)
        return {"stream_key": new_key}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    global _http
    _http = httpx.AsyncClient(timeout=8, limits=httpx.Limits(max_connections=10, max_keepalive_connections=3))


@app.on_event("shutdown")
async def shutdown():
    if _http:
        await _http.aclose()
