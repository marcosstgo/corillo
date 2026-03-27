"""
corillo-api — API pública de streamers: perfiles y regeneración de stream key.
Puerto 3004. Sin dependencias del chat ni de Telegram.
"""
import os, time, secrets, json, glob, asyncio, threading
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pywebpush import webpush, WebPushException

load_dotenv()

PB_URL         = os.environ.get("PB_URL", "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS", "")

VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_MAILTO      = os.environ.get("VAPID_MAILTO", "hello@corillo.live")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://corillo.live", "http://localhost:8080"],
    allow_methods=["GET", "POST", "DELETE"],
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
                "fields": "id,key,display_name,sub,bio,color,twitch,instagram,tiktok,avatar,panels",
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
        handle = r.json().get("key", record_id)
        new_key = secrets.token_urlsafe(24)
        admin_token = await _admin_token()
        r2 = await _http.patch(
            f"{PB_URL}/api/collections/streamers/records/{record_id}",
            headers={"Authorization": admin_token},
            json={"stream_key": new_key, "stream_key_full": f"{handle}?secret={new_key}"},
        )
        if r2.status_code != 200:
            raise HTTPException(status_code=500)
        return {"stream_key": new_key}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500)


# ── Push notifications ──────────────────────────────────────────────────────

@app.get("/push-config")
def push_config():
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503)
    return {"public_key": VAPID_PUBLIC_KEY}


@app.post("/subscribe")
async def subscribe(request: Request):
    try:
        data = await request.json()
        channel      = data.get("channel", "")
        subscription = data.get("subscription", {})
        endpoint     = subscription.get("endpoint", "")
        if not channel or not endpoint:
            raise HTTPException(status_code=400)
        token = await _admin_token()
        r = await _http.get(
            f"{PB_URL}/api/collections/push_subscriptions/records",
            headers={"Authorization": token},
            params={"filter": f'endpoint="{endpoint}" && channel="{channel}"', "perPage": 1},
        )
        if not r.json().get("items"):
            await _http.post(
                f"{PB_URL}/api/collections/push_subscriptions/records",
                headers={"Authorization": token},
                json={"channel": channel, "endpoint": endpoint, "subscription": json.dumps(subscription)},
            )
        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500)


@app.delete("/subscribe")
async def unsubscribe(request: Request):
    try:
        data     = await request.json()
        channel  = data.get("channel", "")
        endpoint = data.get("endpoint", "")
        if not channel or not endpoint:
            raise HTTPException(status_code=400)
        token = await _admin_token()
        r = await _http.get(
            f"{PB_URL}/api/collections/push_subscriptions/records",
            headers={"Authorization": token},
            params={"filter": f'endpoint="{endpoint}" && channel="{channel}"', "perPage": 1},
        )
        items = r.json().get("items", [])
        if items:
            await _http.delete(
                f"{PB_URL}/api/collections/push_subscriptions/records/{items[0]['id']}",
                headers={"Authorization": token},
            )
        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500)


@app.post("/internal/notify")
async def internal_notify(request: Request):
    if request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403)
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503)
    try:
        data    = await request.json()
        path    = data.get("path", "")
        if not path.startswith("live/"):
            raise HTTPException(status_code=400)
        channel = path[5:]

        token = await _admin_token()

        # Suscripciones del canal
        r = await _http.get(
            f"{PB_URL}/api/collections/push_subscriptions/records",
            headers={"Authorization": token},
            params={"filter": f'channel="{channel}"', "perPage": 500},
        )
        items = r.json().get("items", [])
        if not items:
            return {"sent": 0, "stale": 0}

        # Nombre del streamer
        sr = await _http.get(
            f"{PB_URL}/api/collections/streamers/records",
            headers={"Authorization": token},
            params={"filter": f'key="{channel}"', "fields": "display_name", "perPage": 1},
        )
        name = (sr.json().get("items") or [{}])[0].get("display_name", channel.upper())

        payload = json.dumps({
            "title": f"{name} está en vivo",
            "body": "corillo.live · Puerto Rico",
            "url": f"/{channel}/",
            "channel": channel,
        })

        stale = []
        for item in items:
            try:
                raw = item["subscription"]
                sub = raw if isinstance(raw, dict) else json.loads(raw)
                webpush(
                    subscription_info=sub,
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": f"mailto:{VAPID_MAILTO}"},
                )
            except WebPushException as ex:
                if ex.response and ex.response.status_code in (404, 410):
                    stale.append(item["id"])
            except Exception:
                pass

        for rec_id in stale:
            await _http.delete(
                f"{PB_URL}/api/collections/push_subscriptions/records/{rec_id}",
                headers={"Authorization": token},
            )

        return {"sent": len(items) - len(stale), "stale": len(stale)}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500)


@app.get("/clip/{channel}")
async def get_clip(channel: str):
    if not channel or '/' in channel or '..' in channel:
        raise HTTPException(status_code=400)
    files = sorted(glob.glob(f"/var/vods/live/{channel}/*.mp4"), key=os.path.getmtime)
    if not files:
        raise HTTPException(status_code=404, detail="Sin grabación activa")
    latest = files[-1]
    out = f"/tmp/clip_{channel}_{int(time.time())}.mp4"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-sseof", "-30", "-i", latest,
        "-c", "copy", "-movflags", "+faststart", out,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=25)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=504, detail="Timeout generando clip")
    if proc.returncode != 0 or not os.path.exists(out):
        raise HTTPException(status_code=500, detail="Error generando clip")
    def _cleanup():
        time.sleep(120)
        try: os.unlink(out)
        except: pass
    threading.Thread(target=_cleanup, daemon=True).start()
    return FileResponse(out, media_type="video/mp4", filename=f"clip_{channel}.mp4")


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
