"""
corillo-api — API pública de streamers: perfiles y regeneración de stream key.
Puerto 3004. Sin dependencias del chat ni de Telegram.
"""
import os, re, time, secrets, json, glob, asyncio, threading
from datetime import datetime, timezone
from pathlib import Path
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
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
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

_http: httpx.AsyncClient = None

_pb_token: dict = {"token": "", "ts": 0.0}
PB_TOKEN_TTL = 86400


async def _streamer_from_token(auth: str) -> str:
    """Verifica el token del streamer via auth-refresh y retorna su channel key."""
    me = await _http.post(
        f"{PB_URL}/api/collections/streamers/auth-refresh",
        headers={"Authorization": auth},
    )
    if me.status_code != 200:
        raise HTTPException(status_code=401, detail="Token inválido")
    key = me.json().get("record", {}).get("key", "")
    if not key:
        raise HTTPException(status_code=403)
    return key


async def _get_reel(reel_id: str, token: str) -> dict:
    """Obtiene un reel por ID con token admin. Lanza 404 si no existe."""
    r = await _http.get(
        f"{PB_URL}/api/collections/reels/records/{reel_id}",
        headers={"Authorization": token},
        params={"fields": "channel,filepath,filename,public"},
    )
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Reel no encontrado")
    return r.json()


async def _verify_reel_owner(reel_id: str, auth: str, token: str) -> tuple:
    """Verifica que el token autenticado sea el dueño del reel.
    Retorna (reel_record, channel_key)."""
    rec     = await _get_reel(reel_id, token)
    channel = await _streamer_from_token(auth)
    if channel != rec["channel"]:
        raise HTTPException(status_code=403, detail="Este reel no te pertenece")
    return rec, channel


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
                "fields": "id,key,display_name,sub,bio,color,twitch,instagram,tiktok,avatar,panels,stream_title",
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


@app.get("/clip/vod/{vod_id}")
async def get_vod_clip(vod_id: str, t: float = 0):
    if not vod_id or not re.match(r'^[a-zA-Z0-9]+$', vod_id):
        raise HTTPException(status_code=400)
    t = max(0.0, t)
    token = await _admin_token()
    r = await _http.get(
        f"{PB_URL}/api/collections/vods/records/{vod_id}",
        headers={"Authorization": token},
        params={"fields": "channel,filename"},
    )
    if r.status_code != 200:
        raise HTTPException(status_code=404)
    vod = r.json()
    channel  = vod.get("channel", "")
    filename = vod.get("filename", "")
    if not channel or '/' in channel or '..' in channel:
        raise HTTPException(status_code=400)
    if not filename or '/' in filename or '..' in filename:
        raise HTTPException(status_code=400)
    filepath = f"/var/vods/live/{channel}/{filename}"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    out = f"/tmp/vod_clip_{vod_id}_{int(t)}_{int(time.time())}.mp4"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-ss", str(int(t)), "-i", filepath,
        "-t", "30", "-c", "copy", "-movflags", "+faststart", out,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=25)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=504)
    if proc.returncode != 0 or not os.path.exists(out):
        raise HTTPException(status_code=500)
    def _cleanup():
        time.sleep(120)
        try: os.unlink(out)
        except: pass
    threading.Thread(target=_cleanup, daemon=True).start()
    return FileResponse(out, media_type="video/mp4", filename=f"clip_{channel}_{int(t)}s.mp4")


@app.post("/reel")
async def create_reel(request: Request):
    """Genera un reel 9:16 desde un VOD. Requiere auth del streamer propietario."""
    auth = request.headers.get("Authorization", "")
    if not auth:
        raise HTTPException(status_code=401)

    data   = await request.json()
    vod_id = data.get("vod_id", "")
    start  = float(data.get("start", 0))
    end    = float(data.get("end", 60))
    public = bool(data.get("public", False))
    title  = str(data.get("title", ""))[:80]
    # crop_x: posición horizontal normalizada 0.0 (izq) → 1.0 (der). None = center crop.
    crop_x_raw = data.get("crop_x")
    crop_x = float(crop_x_raw) if crop_x_raw is not None else None
    if crop_x is not None:
        crop_x = max(0.0, min(1.0, crop_x))

    # face overlay: region of the source video to composite on top of the 9:16 output.
    # All values normalized 0-1 relative to video dimensions. None = no overlay.
    def _clamp01(v): return max(0.0, min(1.0, float(v)))
    face_x_raw = data.get("face_x")
    face_y_raw = data.get("face_y")
    face_w_raw = data.get("face_w")
    face_h_raw = data.get("face_h")
    use_face = all(v is not None for v in [face_x_raw, face_y_raw, face_w_raw, face_h_raw])
    if use_face:
        face_x = _clamp01(face_x_raw)
        face_y = _clamp01(face_y_raw)
        face_w = max(0.05, _clamp01(face_w_raw))
        face_h = max(0.05, _clamp01(face_h_raw))

    face_pos = data.get("face_pos", "bl")
    if face_pos not in ("tl", "tr", "bl", "br"):
        face_pos = "bl"
    face_shape = data.get("face_shape", "square")
    if face_shape not in ("square", "circle"):
        face_shape = "square"

    if not vod_id:
        raise HTTPException(status_code=400, detail="Falta vod_id")

    duration = end - start
    if duration < 5 or duration > 60:
        raise HTTPException(status_code=400, detail="Duración debe ser entre 5 y 60 segundos")
    if start < 0:
        raise HTTPException(status_code=400, detail="Inicio inválido")

    # Verificar identidad del streamer
    channel = await _streamer_from_token(auth)

    # Obtener info del VOD con token admin
    token = await _admin_token()
    rv = await _http.get(
        f"{PB_URL}/api/collections/vods/records/{vod_id}",
        headers={"Authorization": token},
        params={"fields": "channel,filename,filepath,duration"},
    )
    if rv.status_code != 200:
        raise HTTPException(status_code=404, detail="VOD no encontrado")
    vod = rv.json()

    if vod.get("channel") != channel:
        raise HTTPException(status_code=403, detail="Este VOD no te pertenece")

    vod_filepath = vod.get("filepath", "")
    if not vod_filepath or not os.path.exists(vod_filepath):
        raise HTTPException(status_code=404, detail="Archivo VOD no encontrado en el servidor")

    vod_duration = float(vod.get("duration") or 0)
    if vod_duration > 0 and end > vod_duration:
        raise HTTPException(status_code=400, detail=f"El fin ({end}s) supera la duración del VOD ({vod_duration}s)")

    # Preparar rutas de salida
    reel_dir = Path(f"/var/vods/reels/{channel}")
    reel_dir.mkdir(parents=True, exist_ok=True)
    ts  = int(time.time())
    out = str(reel_dir / f"{ts}.mp4")
    thumb_out = str(reel_dir / f"{ts}.jpg")

    # ffmpeg: crop 9:16 desde posición elegida por el usuario (o centro si no viene)
    # crop=w=ih*9/16 : h=ih : x=(iw-ih*9/16)*crop_x : y=0  → scale 1080×1920
    if crop_x is not None:
        bg_filter = f"crop=ih*9/16:ih:(iw-ih*9/16)*{crop_x:.6f}:0,scale=1080:1920"
    else:
        bg_filter = "scale=-2:1920,crop=1080:1920"

    if use_face:
        # Overlay position in the 9:16 output (16px padding from edges)
        pos_map = {"tl": ("16", "16"), "tr": ("W-w-16", "16"),
                   "bl": ("16", "H-h-16"), "br": ("W-w-16", "H-h-16")}
        ox, oy = pos_map[face_pos]

        if face_shape == "circle":
            # Scale to square, apply circular alpha mask via geq, overlay with alpha
            face_part = (
                f"[0:v]crop=iw*{face_w:.6f}:ih*{face_h:.6f}:iw*{face_x:.6f}:ih*{face_y:.6f},"
                f"scale=360:360,"
                f"format=rgba,"
                f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='255*lte(sqrt((X-180)*(X-180)+(Y-180)*(Y-180)),180)'[face]"
            )
            overlay_expr = f"overlay={ox}:{oy}:format=auto"
        else:
            face_part = (
                f"[0:v]crop=iw*{face_w:.6f}:ih*{face_h:.6f}:iw*{face_x:.6f}:ih*{face_y:.6f},"
                f"scale=360:-2[face]"
            )
            overlay_expr = f"overlay={ox}:{oy}"

        filter_complex = (
            f"[0:v]{bg_filter}[bg];"
            f"{face_part};"
            f"[bg][face]{overlay_expr}[out]"
        )
    else:
        filter_complex = f"[0:v]{bg_filter}[out]"

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-ss", str(int(start)), "-i", vod_filepath,
        "-t", str(int(duration) + 1),
        "-filter_complex", filter_complex,
        "-map", "[out]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=180)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=504, detail="Timeout generando reel")

    if proc.returncode != 0 or not os.path.exists(out):
        raise HTTPException(status_code=500, detail="Error generando reel con ffmpeg")

    # Thumbnail del reel
    thumb_url = ""
    tp = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-ss", "1", "-i", out,
        "-vframes", "1", "-vf", "scale=540:960", "-q:v", "3",
        thumb_out,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(tp.communicate(), timeout=20)
        if os.path.exists(thumb_out):
            thumb_url = f"/vods/reels/{channel}/{ts}.jpg"
    except Exception:
        pass

    size = os.path.getsize(out) if os.path.exists(out) else 0

    # Guardar en PocketBase
    rr = await _http.post(
        f"{PB_URL}/api/collections/reels/records",
        headers={"Authorization": token},
        json={
            "channel":   channel,
            "vod_id":    vod_id,
            "filename":  f"{ts}.mp4",
            "filepath":  out,
            "duration":  int(duration),
            "start_sec": int(start),
            "end_sec":   int(end),
            "thumb":     thumb_url,
            "public":    public,
            "title":     title,
            "size":      size,
            "date":      datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.000Z'),
        },
        timeout=15,
    )
    if rr.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail="Error guardando reel en base de datos")

    rec = rr.json()
    return {
        "id":           rec["id"],
        "filename":     f"{ts}.mp4",
        "thumb":        thumb_url,
        "duration":     int(duration),
        "public":       public,
        "download_url": f"/vods/reels/{channel}/{ts}.mp4",
    }


@app.post("/reel/upload")
async def upload_reel(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    public: str = Form("false"),
    record_id: str = Form(""),
):
    """Sube un video propio como reel. Solo streamers autenticados."""
    auth = request.headers.get("Authorization", "")
    if not auth:
        raise HTTPException(status_code=401)

    # Verificar identidad del streamer
    channel = await _streamer_from_token(auth)

    # Validar tipo MIME
    ct = file.content_type or ""
    if not ct.startswith("video/"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos de video")

    # Leer archivo en memoria (límite 500 MB)
    MAX_SIZE = 500 * 1024 * 1024
    data = await file.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="El archivo supera los 500 MB")

    # Guardar temporal
    reel_dir = Path(f"/var/vods/reels/{channel}")
    reel_dir.mkdir(parents=True, exist_ok=True)
    ts  = int(time.time())
    tmp = str(reel_dir / f"{ts}_upload_tmp{Path(file.filename or '.mp4').suffix}")
    out = str(reel_dir / f"{ts}.mp4")
    thumb_out = str(reel_dir / f"{ts}.jpg")

    with open(tmp, "wb") as f_:
        f_.write(data)

    # Obtener duración con ffprobe
    pp = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "format=duration", "-of", "csv=p=0", tmp,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await pp.communicate()
    try:
        duration = float(stdout.decode().strip())
    except Exception:
        os.unlink(tmp)
        raise HTTPException(status_code=400, detail="No se pudo leer la duración del video")

    if duration > 60:
        os.unlink(tmp)
        raise HTTPException(status_code=400, detail="El video no puede superar los 60 segundos")

    # Detectar dimensiones para saber si es 16:9 o ya está en 9:16
    dp = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", tmp,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    dim_out, _ = await dp.communicate()
    try:
        w, h = [int(x) for x in dim_out.decode().strip().split(",")]
        is_landscape = w > h
    except Exception:
        is_landscape = False

    if is_landscape:
        # 16:9 → center crop al centro para 9:16
        vf_args = ["-vf", "scale=-2:1920,crop=1080:1920"]
    else:
        # Ya es 9:16 o portrait — solo escalar a 1080×1920 sin cortar
        vf_args = ["-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"]

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", tmp,
        *vf_args,
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=300)
    except asyncio.TimeoutError:
        proc.kill()
        os.unlink(tmp)
        raise HTTPException(status_code=504, detail="Timeout procesando video")

    os.unlink(tmp)

    if proc.returncode != 0 or not os.path.exists(out):
        raise HTTPException(status_code=500, detail="Error procesando el video")

    # Thumbnail
    thumb_url = ""
    tp = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-ss", "1", "-i", out,
        "-vframes", "1", "-vf", "scale=540:960", "-q:v", "3",
        thumb_out,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(tp.communicate(), timeout=20)
        if os.path.exists(thumb_out):
            thumb_url = f"/vods/reels/{channel}/{ts}.jpg"
    except Exception:
        pass

    size = os.path.getsize(out) if os.path.exists(out) else 0
    is_public = public.lower() in ("true", "1", "yes")
    token = await _admin_token()

    rr = await _http.post(
        f"{PB_URL}/api/collections/reels/records",
        headers={"Authorization": token},
        json={
            "channel":   channel,
            "vod_id":    "",
            "filename":  f"{ts}.mp4",
            "filepath":  out,
            "duration":  int(duration),
            "start_sec": 0,
            "end_sec":   int(duration),
            "thumb":     thumb_url,
            "public":    is_public,
            "title":     title.strip()[:120],
            "size":      size,
            "date":      datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.000Z'),
        },
        timeout=15,
    )
    if rr.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail="Error guardando reel en base de datos")

    rec = rr.json()
    return {
        "id":           rec["id"],
        "filename":     f"{ts}.mp4",
        "thumb":        thumb_url,
        "duration":     int(duration),
        "public":       is_public,
        "download_url": f"/vods/reels/{channel}/{ts}.mp4",
    }


@app.delete("/reel/{reel_id}")
async def delete_reel(reel_id: str, request: Request):
    """Elimina un reel. Solo el streamer propietario puede borrarlo."""
    auth = request.headers.get("Authorization", "")
    if not auth:
        raise HTTPException(status_code=401)

    token       = await _admin_token()
    rec, _      = await _verify_reel_owner(reel_id, auth, token)

    # Borrar archivos físicos
    fp = Path(rec.get("filepath", ""))
    fp.unlink(missing_ok=True)
    fp.with_suffix(".jpg").unlink(missing_ok=True)

    # Borrar registro en PocketBase
    await _http.delete(
        f"{PB_URL}/api/collections/reels/records/{reel_id}",
        headers={"Authorization": token},
    )
    return {"ok": True}


@app.delete("/vod/{vod_id}")
async def delete_vod(vod_id: str, request: Request):
    """Elimina un VOD. Solo el streamer propietario puede borrarlo."""
    auth = request.headers.get("Authorization", "")
    if not auth:
        raise HTTPException(status_code=401)

    channel = await _streamer_from_token(auth)
    token   = await _admin_token()

    # Obtener el registro del VOD
    rv = await _http.get(
        f"{PB_URL}/api/collections/vods/records/{vod_id}",
        headers={"Authorization": token},
        params={"fields": "channel,filepath,filename"},
    )
    if rv.status_code != 200:
        raise HTTPException(status_code=404, detail="VOD no encontrado")
    vod = rv.json()

    # Verificar ownership
    if vod.get("channel") != channel:
        raise HTTPException(status_code=403, detail="Este VOD no te pertenece")

    # Borrar archivos físicos — solo bajo /var/vods/live/
    fp = Path(vod.get("filepath", ""))
    if str(fp).startswith("/var/vods/live/"):
        fp.unlink(missing_ok=True)
        fp.with_suffix(".jpg").unlink(missing_ok=True)
        Path(fp.parent / (fp.stem + "-preview.mp4")).unlink(missing_ok=True)

    # Borrar registro en PocketBase
    await _http.delete(
        f"{PB_URL}/api/collections/vods/records/{vod_id}",
        headers={"Authorization": token},
    )
    return {"ok": True}


@app.patch("/reel/{reel_id}/visibility")
async def reel_visibility(reel_id: str, request: Request):
    """Cambia la visibilidad pública de un reel. Solo el propietario puede hacerlo."""
    auth = request.headers.get("Authorization", "")
    if not auth:
        raise HTTPException(status_code=401)

    body   = await request.json()
    public = bool(body.get("public", False))

    token      = await _admin_token()
    _, _channel = await _verify_reel_owner(reel_id, auth, token)

    pr = await _http.patch(
        f"{PB_URL}/api/collections/reels/records/{reel_id}",
        headers={"Authorization": token},
        json={"public": public},
    )
    if pr.status_code != 200:
        raise HTTPException(status_code=500, detail="Error actualizando visibilidad")

    return {"ok": True, "public": public}


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
