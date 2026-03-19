import os, re, time, json, asyncio, random, base64, secrets
from urllib.parse import parse_qs
from fastapi.responses import Response as FastResponse
import httpx, anthropic, aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from system_prompt import SYSTEM

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://corillo.live", "http://localhost:8080"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

ac = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── HTTP client compartido — reutiliza conexiones TCP/TLS (evita handshake en cada llamada) ──
# Para máximo rendimiento, configura MEDIAMTX_HOST=http://{IP_LAN_Pi3Bplus}:9997
# en el .env del Pi 3B para llamar directo a MediaMTX sin pasar por Internet.
MEDIAMTX_HOST = os.environ.get("MEDIAMTX_HOST", "https://corillo.live/mediamtx-api")
THUMBS_HOST   = os.environ.get("THUMBS_HOST",   "https://corillo.live")
DB_PATH       = os.environ.get("DB_PATH", "/home/marcos/corillo-bot/chat.db")
ADMIN_TOKEN      = os.environ.get("ADMIN_TOKEN", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GITHUB_TOKEN     = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO      = os.environ.get("GITHUB_REPO", "marcosstgo/corillo")
GH_API           = "https://api.github.com"
PB_URL           = os.environ.get("PB_URL", "https://pb.corillo.live")
PB_ADMIN_EMAIL   = os.environ.get("PB_ADMIN_EMAIL", "")
PB_ADMIN_PASS    = os.environ.get("PB_ADMIN_PASS", "")

STREAMER_COLORS = [
    "linear-gradient(135deg,#74b9ff,#0984e3)",
    "linear-gradient(135deg,#55efc4,#00b894)",
    "linear-gradient(135deg,#fd79a8,#e84393)",
    "linear-gradient(135deg,#fdcb6e,#e17055)",
    "linear-gradient(135deg,#a29bfe,#6c5ce7)",
    "linear-gradient(135deg,#00cec9,#00838f)",
    "linear-gradient(135deg,#ff7675,#d63031)",
    "linear-gradient(135deg,#ff9f43,#e06010)",
]

_http: httpx.AsyncClient = None   # inicializado en startup
_db:   aiosqlite.Connection = None  # conexión SQLite persistente

# Caché de estado en vivo — evita llamadas redundantes desde múltiples fuentes
_live_cache: dict = {"data": [], "ts": 0.0}
LIVE_CACHE_TTL = 12  # segundos

# Caché de thumbnails — evita re-descargar 50-150 KB en cada comentario del bot
_thumb_cache: dict = {}
THUMB_CACHE_TTL = 35  # segundos (FFmpeg los refresca cada 30s)

# Caché de stream keys de Pocketbase — evita query en cada intento de publish
_key_cache: dict = {}   # channel_key → {"stream_key": str, "ts": float}
KEY_CACHE_TTL = 60      # segundos

# Token de admin PB cacheado — se renueva solo cuando expira
_pb_token: dict = {"token": "", "ts": 0.0}
PB_TOKEN_TTL = 86400    # 24 horas

NAMES = [
    "Coqui","Pitirre","Manatí","Gandule","Sofrito","Tostón",
    "Colmado","Boricua","Mofongo","Platano","Lechón","Bacalao",
    "Chinchorro","Aguacate","Tembleque","Pernil","Añejo","Pilón",
    "BadBunny","Coquí","Chulería","Alcapurria","Bacalaíto",
    "Sorullito","AyBendito","Algarete","Bomba","Plena","Coquito",
]

class Msg(BaseModel):
    message: str

class JoinRequest(BaseModel):
    handle:    str
    nombre:    str
    email:     str
    contenido: str
    plataforma: str = ""
    mensaje:   str = ""
    hp:        str = ""   # honeypot — debe llegar vacío

# Rate limit: max 3 envíos por IP por hora
_join_rl: dict[str, list] = {}
JOIN_RL_MAX    = 3
JOIN_RL_WINDOW = 3600  # segundos

async def get_live():
    """Retorna streams activos. Usa caché de 12s para evitar llamadas redundantes."""
    now = time.time()
    if now - _live_cache["ts"] < LIVE_CACHE_TTL:
        return _live_cache["data"]
    try:
        r = await _http.get(f"{MEDIAMTX_HOST}/v3/paths/list")
        result = [p for p in r.json().get("items", []) if p.get("ready")]
        _live_cache.update({"data": result, "ts": now})
        return result
    except:
        return _live_cache["data"]  # retorna datos stale si falla la llamada

async def fetch_thumb_b64(channel: str) -> str | None:
    """Retorna thumbnail en base64. Caché de 35s — evita re-descargar el JPEG en cada llamada."""
    now = time.time()
    cached = _thumb_cache.get(channel)
    if cached and (now - cached["ts"]) < THUMB_CACHE_TTL:
        return cached["data"]
    url = f"{THUMBS_HOST}/assets/thumbs/{channel}.jpg"
    try:
        r = await _http.get(url)
        if r.status_code == 200:
            data = base64.standard_b64encode(r.content).decode()
            _thumb_cache[channel] = {"data": data, "ts": now}
            return data
    except:
        pass
    return cached["data"] if cached else None  # retorna stale si falla

async def db_save(channel: str, msg: dict):
    """Persiste un mensaje de chat en SQLite."""
    if msg.get("type") != "message" or not _db:
        return
    await _db.execute(
        "INSERT INTO messages (channel, user, text, ts, bot) VALUES (?, ?, ?, ?, ?)",
        (channel, msg["user"], msg["text"], msg["ts"], 1 if msg.get("bot") else 0),
    )
    await _db.commit()

async def db_history(channel: str, limit: int = 50) -> list:
    """Retorna los últimos N mensajes de un canal desde SQLite."""
    if not _db:
        return []
    _db.row_factory = aiosqlite.Row
    async with _db.execute(
        "SELECT user, text, ts, bot FROM messages WHERE channel=? ORDER BY ts DESC LIMIT ?",
        (channel, limit),
    ) as cur:
        rows = await cur.fetchall()
    return [
        {"type": "message", "user": r["user"], "text": r["text"],
         "ts": r["ts"], "bot": bool(r["bot"])}
        for r in reversed(rows)
    ]

async def _gh_get(path: str) -> tuple[str, str]:
    """Retorna (contenido, sha) de un archivo en GitHub."""
    r = await _http.get(
        f"{GH_API}/repos/{GITHUB_REPO}/contents/{path}",
        headers={"Authorization": f"token {GITHUB_TOKEN}",
                 "Accept": "application/vnd.github.v3+json"},
    )
    data = r.json()
    return base64.b64decode(data["content"]).decode(), data["sha"]

async def _gh_put(path: str, content: str, sha: str | None, message: str):
    """Crea o actualiza un archivo en GitHub."""
    payload = {
        "message": message,
        "content": base64.standard_b64encode(content.encode()).decode(),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    await _http.put(
        f"{GH_API}/repos/{GITHUB_REPO}/contents/{path}",
        headers={"Authorization": f"token {GITHUB_TOKEN}",
                 "Accept": "application/vnd.github.v3+json"},
        json=payload,
    )

async def pb_create_streamer(handle: str, nombre: str, email: str, color: str):
    """Crea cuenta en Pocketbase y envía email de reset para que el streamer cree su password."""
    if not PB_ADMIN_EMAIL or not PB_ADMIN_PASS or not email:
        return
    try:
        # Auth como admin
        r = await _http.post(
            f"{PB_URL}/api/collections/_superusers/auth-with-password",
            json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
        )
        token = r.json()["token"]
        headers = {"Authorization": token}

        name_up = nombre.upper() if nombre else handle.upper()
        stream_key = secrets.token_urlsafe(24)
        pw = secrets.token_urlsafe(32)

        # Crear cuenta — si ya existe, actualizar email y stream_key
        r = await _http.post(
            f"{PB_URL}/api/collections/streamers/records",
            headers=headers,
            json={
                "email": email,
                "password": pw,
                "passwordConfirm": pw,
                "key": handle,
                "display_name": name_up,
                "color": color,
                "stream_key": stream_key,
                "active": True,
                "emailVisibility": False,
                "verified": True,
            },
        )
        if r.status_code not in (200, 201):
            # Si ya existe, buscar por key y actualizar email
            r2 = await _http.get(
                f"{PB_URL}/api/collections/streamers/records",
                headers=headers,
                params={"filter": f'key="{handle}"'},
            )
            items = r2.json().get("items", [])
            if items:
                rec_id = items[0]["id"]
                await _http.patch(
                    f"{PB_URL}/api/collections/streamers/records/{rec_id}",
                    headers=headers,
                    json={"email": email, "active": True},
                )

        # Enviar email de reset para que el streamer cree su password
        await _http.post(
            f"{PB_URL}/api/collections/streamers/request-password-reset",
            json={"email": email},
        )
    except Exception as e:
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            await _http.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID,
                      "text": f"⚠️ Pocketbase: no se pudo crear cuenta para @{handle}: {e}"},
            )


async def auto_create_streamer(handle: str, nombre: str, contenido: str, email: str = ""):
    """Crea streamers.js entry + player page + STREAMER_NAMES via GitHub API."""
    if not GITHUB_TOKEN:
        return
    try:
        color  = STREAMER_COLORS[hash(handle) % len(STREAMER_COLORS)]
        ava    = (nombre[0] if nombre else handle[0]).upper()
        name_up = nombre.upper() if nombre else handle.upper()
        sub    = contenido[:50] if contenido else "Gaming · CORILLO"

        # 1 — streamers.js
        js, js_sha = await _gh_get("assets/streamers.js")
        new_entry = (
            f"  {{ key:'{handle}', name:'{name_up}', "
            f"sub:'{sub}', ava:'{ava}', color:'{color}', host:false }},"
        )
        if "soon:true" in js:
            js = js.replace("  { key:null,", f"{new_entry}\n  {{ key:null,")
        else:
            js = js.rstrip().rstrip("]").rstrip() + f"\n{new_entry}\n];\n"
        await _gh_put("assets/streamers.js", js, js_sha,
                      f"feat: add streamer {handle} [auto]")

        # 2 — player page desde template katatonia
        tpl, _ = await _gh_get("katatonia/index.html")
        player = (tpl
                  .replace("KATATONIA", name_up)
                  .replace("/katatonia/", f"/{handle}/")
                  .replace("katatonia", handle))
        await _gh_put(f"{handle}/index.html", player, None,
                      f"feat: add player page for {handle} [auto]")

        # 3 — STREAMER_NAMES en server.py
        py, py_sha = await _gh_get("chat/server.py")
        name_fmt = nombre.title().replace(" ", "") if nombre else handle.title()
        sentinel = "# AUTO_STREAMER_NAMES_END"
        py = py.replace(
            sentinel,
            f'"{handle}": "{name_fmt}",\n    {sentinel}'
        )
        await _gh_put("chat/server.py", py, py_sha,
                      f"feat: add {handle} to STREAMER_NAMES [auto]")

        # Crear cuenta en Pocketbase y enviar email al streamer
        await pb_create_streamer(handle, nombre, email, color)

        # Notificar por Telegram
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            pb_note = f" · email enviado a {email}" if email else ""
            await _http.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID,
                      "text": f"🚀 Canal @{handle} creado — deploy en curso (~1 min){pb_note}",
                      "parse_mode": "Markdown"},
            )
    except Exception as e:
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            await _http.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID,
                      "text": f"❌ Error creando @{handle}: {e}"},
            )

async def _telegram(lines: list[str], handle: str = ""):
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "\n".join(lines),
            "parse_mode": "Markdown",
        }
        if handle:
            payload["reply_markup"] = {"inline_keyboard": [[
                {"text": "✅ Aprobar", "callback_data": f"approve:{handle}"},
                {"text": "❌ Rechazar", "callback_data": f"reject:{handle}"},
            ]]}
        await _http.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=payload,
        )
    except:
        pass

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    cb = data.get("callback_query")
    if not cb:
        return {"ok": True}

    # Verificar que viene del chat autorizado
    chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
    if chat_id != TELEGRAM_CHAT_ID:
        return {"ok": True}

    action, _, handle = cb["data"].partition(":")
    msg_id = cb["message"]["message_id"]
    original_text = cb["message"].get("text", "")

    if action == "approve":
        await _db.execute(
            "UPDATE join_requests SET status='approved' WHERE handle=? AND status='pending'", (handle,)
        )
        await _db.commit()
        # Obtener datos del solicitante para crear el streamer
        _db.row_factory = aiosqlite.Row
        async with _db.execute(
            "SELECT nombre, email, contenido FROM join_requests WHERE handle=? ORDER BY ts DESC LIMIT 1",
            (handle,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            asyncio.create_task(auto_create_streamer(handle, row["nombre"], row["contenido"], row["email"]))
        new_text = original_text + "\n\n✅ *APROBADO* — creando canal automáticamente..."
        answer_text = f"✅ {handle} aprobado"
    elif action == "reject":
        await _db.execute(
            "UPDATE join_requests SET status='rejected' WHERE handle=? AND status='pending'", (handle,)
        )
        await _db.commit()
        new_text = original_text + "\n\n❌ *RECHAZADO*"
        answer_text = f"❌ {handle} rechazado"
    else:
        return {"ok": True}

    # Editar el mensaje para quitar los botones y mostrar el resultado
    try:
        await _http.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
            json={"chat_id": TELEGRAM_CHAT_ID, "message_id": msg_id,
                  "text": new_text, "parse_mode": "Markdown"},
        )
        await _http.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": cb["id"], "text": answer_text},
        )
    except:
        pass
    return {"ok": True}

async def _pb_admin_token() -> str:
    """Retorna token de admin PB con caché de 24h."""
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


async def _validate_stream_key(channel_key: str, secret: str) -> bool:
    """Valida stream key contra Pocketbase con caché de 60s."""
    now = time.time()
    cached = _key_cache.get(channel_key)
    if cached and now - cached["ts"] < KEY_CACHE_TTL:
        return cached["stream_key"] == secret
    try:
        token = await _pb_admin_token()
        r = await _http.get(
            f"{PB_URL}/api/collections/streamers/records",
            headers={"Authorization": token},
            params={"filter": f'key="{channel_key}" && active=true', "fields": "stream_key"},
        )
        items = r.json().get("items", [])
        if not items:
            return False
        sk = items[0]["stream_key"]
        _key_cache[channel_key] = {"stream_key": sk, "ts": now}
        return sk == secret
    except:
        return False


@app.post("/mtx-auth")
async def mtx_auth(request: Request):
    """Webhook de autenticación para MediaMTX."""
    try:
        data = await request.json()
    except Exception:
        return FastResponse(status_code=401)

    action = data.get("action", "")
    path   = data.get("path", "")    # e.g. "live/katatonia"
    ip     = data.get("ip", "")
    query  = data.get("query", "")   # e.g. "secret=ABC123"

    # Viewers y playback — libre para todos
    if action in ("read", "playback"):
        return FastResponse(status_code=200)

    # API/metrics/pprof — solo localhost
    if action in ("api", "metrics", "pprof"):
        if ip in ("127.0.0.1", "::1"):
            return FastResponse(status_code=200)
        return FastResponse(status_code=401)

    # Publish — validar stream key
    if action == "publish":
        if not PB_ADMIN_EMAIL or not PB_ADMIN_PASS:
            return FastResponse(status_code=200)  # PB no configurado → permitir (compatibilidad)

        params = parse_qs(query.lstrip("?"))
        secret = (params.get("secret") or params.get("pass") or [None])[0]

        if not secret:
            return FastResponse(status_code=401)

        # Extraer canal: "live/katatonia" → "katatonia"
        channel_key = path.removeprefix("live/").split("?")[0]

        valid = await _validate_stream_key(channel_key, secret)
        return FastResponse(status_code=200 if valid else 401)

    return FastResponse(status_code=401)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/join")
async def submit_join(req: JoinRequest, request: Request):
    # Honeypot — si el campo hp viene relleno es un bot; fingir éxito
    if req.hp:
        return {"ok": True}

    # Rate limit por IP
    ip = (request.headers.get("x-real-ip")
          or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else "unknown"))
    now = time.time()
    hits = [t for t in _join_rl.get(ip, []) if now - t < JOIN_RL_WINDOW]
    if len(hits) >= JOIN_RL_MAX:
        raise HTTPException(status_code=429, detail="Demasiados intentos. Intenta más tarde.")
    hits.append(now)
    _join_rl[ip] = hits

    handle = req.handle.strip().lower()
    if not re.match(r'^[a-z0-9_]{3,24}$', handle):
        raise HTTPException(status_code=400, detail="Handle inválido")
    if not req.nombre.strip() or not req.contenido.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="Faltan campos requeridos")

    # Handle duplicado pendiente
    async with _db.execute(
        "SELECT id FROM join_requests WHERE handle=? AND status='pending'", (handle,)
    ) as cur:
        if await cur.fetchone():
            raise HTTPException(status_code=409, detail="Este handle ya tiene una solicitud pendiente.")
    await _db.execute(
        "INSERT INTO join_requests (handle, nombre, email, contenido, plataforma, mensaje, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (handle, req.nombre.strip()[:60], req.email.strip()[:120], req.contenido.strip()[:120],
         req.plataforma.strip()[:60], req.mensaje.strip()[:300], time.time()),
    )
    await _db.commit()
    # Notificar por Telegram
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        lines = [f"📥 *Nueva solicitud — @{handle}*"]
        lines.append(f"Nombre: {req.nombre.strip()[:60]}")
        lines.append(f"Email: {req.email.strip()[:120]}")
        lines.append(f"Contenido: {req.contenido.strip()[:120]}")
        if req.plataforma.strip():
            lines.append(f"Plataforma: {req.plataforma.strip()[:60]}")
        if req.mensaje.strip():
            lines.append(f"Mensaje: {req.mensaje.strip()[:200]}")
        asyncio.create_task(_telegram(lines, handle=handle))

    # Notificar al host en el chat de katatonia
    lines = [f"📥 Nueva solicitud de canal — @{handle}"]
    lines.append(f"Nombre: {req.nombre.strip()[:60]}")
    lines.append(f"Email: {req.email.strip()[:120]}")
    lines.append(f"Contenido: {req.contenido.strip()[:120]}")
    if req.plataforma.strip():
        lines.append(f"Plataforma: {req.plataforma.strip()[:60]}")
    if req.mensaje.strip():
        lines.append(f"Mensaje: {req.mensaje.strip()[:200]}")
    room = get_room("katatonia")
    await room.broadcast({
        "type": "message",
        "user": "CORILLO BOT",
        "text": " · ".join(lines),
        "ts": time.time(),
        "bot": True,
    })
    return {"ok": True}

@app.get("/admin/requests")
async def admin_requests(token: str = ""):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    _db.row_factory = aiosqlite.Row
    async with _db.execute(
        "SELECT id, handle, nombre, contenido, plataforma, mensaje, ts, status "
        "FROM join_requests ORDER BY ts DESC"
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]

@app.post("/message")
async def chat(body: Msg):
    live = await get_live()
    status = ("En vivo ahora:\n" + "\n".join(
        f"- {p['name']}: {len(p.get('readers', []))} viewers" for p in live
    )) if live else "Sin streams en vivo."
    res = ac.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM + f"\n\n{status}",
        messages=[{"role": "user", "content": body.message}],
    )
    return {"reply": res.content[0].text}

# ── Digest (2 min cache) ─────────────────────────────────────────
_digest = {"text": "", "ts": 0}
DIGEST_TTL = 120

@app.get("/digest")
async def digest():
    if time.time() - _digest["ts"] < DIGEST_TTL and _digest["text"]:
        return {"digest": _digest["text"]}

    live = await get_live()
    if live:
        lines = "\n".join(f"- {p['name']}: {len(p.get('readers', []))} viewers" for p in live)
        prompt = (
            f"Estado actual de CORILLO:\n{lines}\n\n"
            "Escribe UNA sola frase corta y casual sobre quién está en vivo ahora. "
            "Sin saludos, sin hashtags, sin emojis. Solo la frase."
        )
    else:
        prompt = (
            "No hay streams en vivo en CORILLO ahora mismo. "
            "Escribe UNA sola frase corta y casual al estilo boricua para invitar a la gente a conectarse más tarde. "
            "Sin saludos, sin hashtags, sin emojis. Solo la frase."
        )

    res = ac.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    _digest["text"] = res.content[0].text.strip()
    _digest["ts"] = time.time()
    return {"digest": _digest["text"]}

# ── WebSocket Chat ───────────────────────────────────────────────
RATE_LIMIT = 1.0  # segundos mínimos entre mensajes

class Room:
    def __init__(self, channel: str):
        self.channel = channel
        self.clients: dict = {}    # websocket → username
        self.history: list = []    # últimos 50 mensajes (cache en RAM)
        self.last_msg: dict = {}   # websocket → timestamp último mensaje
        self._vision_task = None   # loop de comentarios espontáneos
        self._last_bot_reply = 0.0 # última vez que el bot habló (greet o @bot)

    async def join(self, ws: WebSocket, requested: str = "") -> str:
        await ws.accept()
        if requested and 3 <= len(requested) <= 40 and ' ' not in requested:
            username = requested
        else:
            username = random.choice(NAMES) + "_" + str(random.randint(10, 99))
        self.clients[ws] = username
        self.last_msg[ws] = 0.0
        # Cargar historial desde SQLite si la RAM está vacía (primer viewer tras restart)
        if not self.history:
            self.history = await db_history(self.channel)
        return username

    def leave(self, ws: WebSocket):
        self.clients.pop(ws, None)
        self.last_msg.pop(ws, None)

    def check_rate(self, ws: WebSocket) -> bool:
        now = time.time()
        if now - self.last_msg.get(ws, 0) < RATE_LIMIT:
            return False
        self.last_msg[ws] = now
        return True

    async def broadcast(self, msg: dict):
        self.history.append(msg)
        if len(self.history) > 50:
            self.history = self.history[-50:]
        asyncio.create_task(db_save(self.channel, msg))
        for ws in list(self.clients):
            try:
                await ws.send_json(msg)
            except:
                self.clients.pop(ws, None)

rooms: dict = {}

def get_room(channel: str) -> Room:
    if channel not in rooms:
        rooms[channel] = Room(channel)
    return rooms[channel]

@app.websocket("/ws/{channel}")
async def ws_chat(ws: WebSocket, channel: str):
    room = get_room(channel)
    requested = ws.query_params.get("user", "").strip()[:40]
    username = await room.join(ws, requested)

    # Arrancar vision loop si no hay uno activo
    if room._vision_task is None or room._vision_task.done():
        room._vision_task = asyncio.create_task(vision_loop(room, channel))

    # Bienvenida + historial
    await ws.send_json({"type": "welcome", "user": username})
    for msg in room.history:
        await ws.send_json(msg)

    try:
        while True:
            data = await ws.receive_text()
            try:
                payload = json.loads(data)
            except:
                continue
            text = str(payload.get("text", "")).strip()[:280]
            if not text:
                continue

            if not room.check_rate(ws):
                await ws.send_json({"type": "system", "text": "Tranquilo, no tan rápido. 🐢"})
                continue

            msg = {
                "type": "message",
                "user": username,
                "text": text,
                "ts": time.time(),
                "bot": False,
            }
            await room.broadcast(msg)

            if "@bot" in text.lower():
                query = text.lower().split("@bot", 1)[-1].strip() or "hola"
                asyncio.create_task(bot_reply(room, query, channel))

    except WebSocketDisconnect:
        room.leave(ws)

async def bot_reply(room: Room, query: str, channel: str = ""):
    live = await get_live()
    status = ("En vivo:\n" + "\n".join(
        f"- {p['name']}: {len(p.get('readers', []))} viewers" for p in live
    )) if live else "Sin streams en vivo."

    # Incluir thumbnail del canal si está disponible
    b64 = await fetch_thumb_b64(channel) if channel else None
    user_content = []
    if b64:
        user_content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })
    user_content.append({"type": "text", "text": query})

    try:
        res = await asyncio.to_thread(
            ac.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=SYSTEM + f"\n\n{status}",
            messages=[{"role": "user", "content": user_content}],
        )
        reply = res.content[0].text.strip()
    except:
        reply = "No pude responder ahora mismo."

    room._last_bot_reply = time.time()
    await room.broadcast({
        "type": "message",
        "user": "CORILLO BOT",
        "text": reply,
        "ts": time.time(),
        "bot": True,
    })

VISION_SYSTEM = (
    "Eres un viewer más del stream. Estás viendo una captura de pantalla del stream en vivo. "
    "Reacciona a lo que ves en la imagen con UN comentario MUY corto y casual en español, "
    "como lo haría alguien del crew boricua mirando el stream. "
    "Máximo 1 frase breve. Sin saludos, sin hashtags. Máximo 1 emoji si aplica. "
    "Reacciona específicamente a lo que se ve en pantalla."
)

async def bot_vision_comment(room: Room, channel: str):
    b64 = await fetch_thumb_b64(channel)
    if not b64:
        return
    try:
        res = await asyncio.to_thread(
            ac.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            system=VISION_SYSTEM,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": "¿Qué está pasando en el stream?"},
            ]}],
        )
        comment = res.content[0].text.strip()
        if comment:
            await room.broadcast({
                "type": "message",
                "user": "CORILLO BOT",
                "text": comment,
                "ts": time.time(),
                "bot": True,
            })
    except:
        pass

VISION_INTERVAL = 600  # 10 minutos entre comentarios espontáneos

async def vision_loop(room: Room, channel: str):
    # Espera inicial — misma que el intervalo para no pilar encima del saludo
    await asyncio.sleep(VISION_INTERVAL)
    while len(room.clients) > 0:
        live = await get_live()
        live_keys = {p["name"].removeprefix("live/") for p in live}
        # Si el bot ya habló en los últimos 10 min (greet o @bot), saltar este ciclo
        if channel in live_keys and time.time() - room._last_bot_reply >= VISION_INTERVAL:
            await bot_vision_comment(room, channel)
        await asyncio.sleep(VISION_INTERVAL)

# ── STREAMER GREETER ─────────────────────────────────────────────
STREAMER_NAMES = {
    "katatonia":      "Katatonia",
    "tea":            "Tea",
    "mira_sanganooo": "Mira_Sanganooo",
    "404":            "404",
    "elbala":         "Elbala",
    "marcos":         "Marcos",
    "pataecabra":     "Pataecabra",
    "streamerpro":    "StreamerPro",
    "radblaster":     "Radblaster",
    "elhermanoquiles":"ElHermanoQuiles",
    "kamikazepr":     "KamikazePR",
    # AUTO_STREAMER_NAMES_END
}

_prev_live: set = set()
_greeted_at: dict = {}  # channel → timestamp del último saludo
GREET_COOLDOWN = 7200   # 2 horas — no saludar de nuevo si el stream cae y vuelve

async def greet_streamer(room: Room, channel: str):
    # Verificar que el stream sigue activo antes de saludar (evita race condition)
    live = await get_live()
    if channel not in {p["name"].removeprefix("live/") for p in live}:
        return
    name = STREAMER_NAMES.get(channel, channel.upper())
    try:
        res = await asyncio.to_thread(
            ac.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            system=SYSTEM,
            messages=[{"role": "user", "content": (
                f"{name} acaba de empezar su stream en CORILLO. "
                "Escríbele un saludo corto y entusiasta en español boricua, "
                "como parte del crew dándole la bienvenida. "
                "1 frase máximo. Sin hashtags, sin emojis (máx 1)."
            )}],
        )
        greeting = res.content[0].text.strip()
    except:
        greeting = f"¡Wepa {name}, arriba el stream! 🔥"

    room._last_bot_reply = time.time()
    await room.broadcast({
        "type": "message",
        "user": "CORILLO BOT",
        "text": greeting,
        "ts": time.time(),
        "bot": True,
    })

async def live_monitor():
    global _prev_live
    await asyncio.sleep(20)  # espera inicial al arrancar el servidor
    # Primera poll — establece baseline sin saludar (evita falsos saludos al reiniciar)
    try:
        live = await get_live()
        _prev_live = {p["name"].removeprefix("live/") for p in live}
    except:
        pass
    while True:
        try:
            live = await get_live()
            current_live = {p["name"].removeprefix("live/") for p in live}
            newly_live = current_live - _prev_live
            for ch in newly_live:
                now = time.time()
                if now - _greeted_at.get(ch, 0) > GREET_COOLDOWN:
                    _greeted_at[ch] = now
                    room = get_room(ch)
                    asyncio.create_task(greet_streamer(room, ch))
                    name = STREAMER_NAMES.get(ch, ch.upper())
                    asyncio.create_task(_telegram([
                        f"🔴 *{name} está en vivo*",
                        f"corillo.live/{ch}",
                    ]))
            _prev_live = current_live
        except:
            pass
        await asyncio.sleep(15)

@app.on_event("startup")
async def startup():
    global _http, _db
    _db = await aiosqlite.connect(DB_PATH)
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA synchronous=NORMAL")
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            user    TEXT NOT NULL,
            text    TEXT NOT NULL,
            ts      REAL NOT NULL,
            bot     INTEGER NOT NULL DEFAULT 0
        )
    """)
    await _db.execute(
        "CREATE INDEX IF NOT EXISTS idx_channel_ts ON messages(channel, ts)"
    )
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS join_requests (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            handle     TEXT NOT NULL,
            nombre     TEXT NOT NULL,
            email      TEXT DEFAULT '',
            contenido  TEXT NOT NULL,
            plataforma TEXT DEFAULT '',
            mensaje    TEXT DEFAULT '',
            ts         REAL NOT NULL,
            status     TEXT DEFAULT 'pending'
        )
    """)
    await _db.commit()
    _http = httpx.AsyncClient(
        timeout=8,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
    )
    asyncio.create_task(live_monitor())
    # Registrar webhook de Telegram
    if TELEGRAM_TOKEN:
        try:
            await _http.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                json={"url": "https://corillo.live/chat-api/telegram-webhook",
                      "allowed_updates": ["callback_query"]},
            )
        except:
            pass

@app.on_event("shutdown")
async def shutdown():
    if _http:
        await _http.aclose()
    if _db:
        await _db.close()
