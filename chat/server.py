"""
corillo-bot — Chat en vivo, IA, WebSocket.
Puerto 3001. Solo responsabilidad: chat.
"""
import os, re, time, json, asyncio, random, base64
import httpx, aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from system_prompt import SYSTEM

load_dotenv()

MEDIAMTX_HOST = os.environ.get("MEDIAMTX_HOST", "http://10.77.0.2:9997")        # corillo-server por el túnel WireGuard
THUMBS_HOST   = os.environ.get("THUMBS_HOST",   "https://media.corillo.live")
DB_PATH       = os.environ.get("DB_PATH", "/home/corillo-adm/corillo-chat/chat.db")

# Seguridad (auditoría 31-oct-2026)
ORIGENES_WS  = re.compile(r"^https://((www\.)?corillo\.live|[a-z0-9-]+\.corillo\.pages\.dev)$|^http://localhost(:\d+)?$")
CANAL_RE     = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
USUARIO_RE   = re.compile(r"^w{3,24}$")    # w acepta tildes y ñ (Lechón_81)
MAX_SALAS    = 200          # salas en memoria (antes cualquier nombre de canal creaba una)
MAX_EN_SALA  = 500
BOT_PAUSA    = 8.0          # segundos mínimos entre respuestas del bot en una sala
BOT_MAX_DIA  = 400          # tope diario de llamadas a la IA por @bot (gasta DeepSeek/Groq)
_bot_uso     = {"dia": "", "n": 0}


def _es_nombre_del_bot(nombre: str) -> bool:
    """Nadie puede llamarse como el bot (antes 'CORILLO BOT' con un espacio raro pasaba)."""
    plano = re.sub(r"[^a-z]", "", nombre.lower())
    return "corillobot" in plano or plano in ("bot", "corillo", "admin", "moderador")


def _bot_puede() -> bool:
    hoy = time.strftime("%Y-%m-%d")
    if _bot_uso["dia"] != hoy:
        _bot_uso.update({"dia": hoy, "n": 0})
    if _bot_uso["n"] >= BOT_MAX_DIA:
        return False
    _bot_uso["n"] += 1
    return True

DISCORD_URL   = os.environ.get("DISCORD_URL",   "")
INSTAGRAM_URL = os.environ.get("INSTAGRAM_URL", "")

GROQ_API_KEY        = os.environ.get("GROQ_API_KEY",   "")
GROQ_MODEL          = os.environ.get("GROQ_MODEL",    "openai/gpt-oss-120b")   # llama-3.3-70b-versatile ya no existe en Groq (404)
DEEPSEEK_API_KEY    = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL      = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "")
GEMINI_VISION_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")


def _clean(t: str) -> str:
    """El chat no renderiza markdown: quita ** y __ que algunos modelos añaden."""
    return re.sub(r"\*\*|__", "", t).strip()


async def deepseek(system: str, prompt: str, max_tokens: int) -> str:
    r = await _http.post(
        "https://api.deepseek.com/chat/completions",
        json={
            "model": DEEPSEEK_MODEL, "max_tokens": max_tokens, "thinking": {"type": "disabled"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        },
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        timeout=30,
    )
    return r.json()["choices"][0]["message"]["content"].strip()


async def _groq_call(system: str, prompt: str, max_tokens: int) -> str:
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": max_tokens * 3,   # gpt-oss gasta parte en razonamiento
    }
    if "gpt-oss" in GROQ_MODEL:
        payload["reasoning_effort"] = "low"
    r = await _http.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        timeout=30,
    )
    return r.json()["choices"][0]["message"]["content"].strip()


async def groq(system: str, prompt: str, max_tokens: int = 150) -> str:
    """Nombre histórico. Respuestas de texto: DeepSeek primero, Groq de respaldo."""
    if DEEPSEEK_API_KEY:
        try:
            return _clean(await deepseek(system, prompt, max_tokens))
        except Exception as e:
            print(f"[bot] deepseek falló, uso Groq: {type(e).__name__}: {e}", flush=True)
    return _clean(await _groq_call(system, prompt, max_tokens))


async def gemini_vision(system: str, prompt: str, b64: str, max_tokens: int = 60) -> str:
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "thinkingConfig": {"thinkingBudget": 0}},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_VISION_MODEL}:generateContent?key={GEMINI_API_KEY}"
    r = await _http.post(url, json=payload, timeout=30)
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

# Orígenes que pueden llamar a esta API desde el navegador (la página vive en Cloudflare Pages, otro dominio).
ORIGENES = ["https://corillo.live", "https://www.corillo.live", "http://localhost:4321", "http://localhost:8080"] + \
    [o.strip() for o in os.environ.get("CORS_EXTRA", "").split(",") if o.strip()]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_http: httpx.AsyncClient = None
_db:   aiosqlite.Connection = None

_live_cache: dict = {"data": [], "ts": 0.0}
LIVE_CACHE_TTL = 12

_thumb_cache: dict = {}
THUMB_CACHE_TTL = 35

NAMES = [
    "Coqui","Pitirre","Manatí","Gandule","Sofrito","Tostón",
    "Colmado","Boricua","Mofongo","Platano","Lechón","Bacalao",
    "Chinchorro","Aguacate","Tembleque","Pernil","Añejo","Pilón",
    "BadBunny","Coquí","Chulería","Alcapurria","Bacalaíto",
    "Sorullito","AyBendito","Algarete","Bomba","Plena","Coquito",
]

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
}


async def get_live():
    now = time.time()
    if now - _live_cache["ts"] < LIVE_CACHE_TTL:
        return _live_cache["data"]
    try:
        r = await _http.get(f"{MEDIAMTX_HOST}/v3/paths/list")
        # Sin las variantes internas (_low 720p, _rtc WebRTC): no son streams aparte (antes el bot las
        # contaba como canales y saludaba a "katatonia_low").
        result = [p for p in r.json().get("items", [])
                  if p.get("ready") and not p["name"].endswith(("_low", "_rtc"))]
        _live_cache.update({"data": result, "ts": now})
        return result
    except:
        return _live_cache["data"]


async def fetch_thumb_b64(channel: str) -> str | None:
    now = time.time()
    cached = _thumb_cache.get(channel)
    if cached and (now - cached["ts"]) < THUMB_CACHE_TTL:
        return cached["data"]
    try:
        r = await _http.get(f"{THUMBS_HOST}/assets/thumbs/{channel}.jpg")
        if r.status_code == 200:
            data = base64.standard_b64encode(r.content).decode()
            _thumb_cache[channel] = {"data": data, "ts": now}
            return data
    except:
        pass
    return cached["data"] if cached else None


async def db_save(channel: str, msg: dict):
    if msg.get("type") != "message" or not _db:
        return
    await _db.execute(
        "INSERT INTO messages (channel, user, text, ts, bot) VALUES (?, ?, ?, ?, ?)",
        (channel, msg["user"], msg["text"], msg["ts"], 1 if msg.get("bot") else 0),
    )
    await _db.commit()


async def db_history(channel: str, limit: int = 50) -> list:
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


@app.get("/health")
def health():
    return {"status": "ok"}


# ── WebSocket Chat ────────────────────────────────────────────────
RATE_LIMIT = 1.0


class Room:
    def __init__(self, channel: str):
        self.channel = channel
        self.clients: dict = {}
        self.history: list = []
        self.last_msg: dict = {}
        self._vision_task = None
        self._last_bot_reply = 0.0

    async def join(self, ws: WebSocket, requested: str = "") -> str:
        await ws.accept()
        if USUARIO_RE.match(requested) and not _es_nombre_del_bot(requested):
            username = requested
        else:
            username = random.choice(NAMES) + "_" + str(random.randint(10, 99))
        self.clients[ws] = username
        self.last_msg[ws] = 0.0
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
    origen = ws.headers.get("origin", "")
    if not ORIGENES_WS.match(origen) or not CANAL_RE.match(channel):
        await ws.close(code=1008)
        return
    if channel not in rooms and len(rooms) >= MAX_SALAS:
        await ws.close(code=1013)
        return
    room = get_room(channel)
    if len(room.clients) >= MAX_EN_SALA:
        await ws.close(code=1013)
        return
    requested = ws.query_params.get("user", "").strip()[:40]
    username = await room.join(ws, requested)

    if room._vision_task is None or room._vision_task.done():
        room._vision_task = asyncio.create_task(vision_loop(room, channel))

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
            msg = {"type": "message", "user": username, "text": text, "ts": time.time(), "bot": False}
            await room.broadcast(msg)
            if text.startswith("!"):
                asyncio.create_task(handle_command(room, channel, text))
            elif "@bot" in text.lower():
                if time.time() - room._last_bot_reply < BOT_PAUSA or not _bot_puede():
                    continue
                room._last_bot_reply = time.time()
                query = text.lower().split("@bot", 1)[-1].strip() or "hola"
                asyncio.create_task(bot_reply(room, query, channel))
    except WebSocketDisconnect:
        room.leave(ws)


async def bot_reply(room: Room, query: str, channel: str = ""):
    live = await get_live()
    status = ("En vivo:\n" + "\n".join(
        f"- {p['name']}: {len(p.get('readers', []))} viewers" for p in live
    )) if live else "Sin streams en vivo."
    # VISION DISABLED — re-enable fetch_thumb_b64 and image block when ready
    # b64 = await fetch_thumb_b64(channel) if channel else None
    user_content = []
    # if b64:
    #     user_content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
    user_content.append({"type": "text", "text": query})
    try:
        reply = await groq(SYSTEM + f"\n\n{status}", query, max_tokens=150)
    except:
        reply = "No pude responder ahora mismo."
    room._last_bot_reply = time.time()
    await room.broadcast({"type": "message", "user": "CORILLO BOT", "text": reply, "ts": time.time(), "bot": True})


VISION_SYSTEM = (
    "Eres CORILLO BOT, un viewer más del crew boricua, y tu sello es el sarcasmo cariñoso y el humor. "
    "Estás viendo una captura de pantalla del stream en vivo. Suelta UN comentario MUY corto, gracioso y con chispa "
    "sobre lo que se ve: vacila al streamer (una muerte, el desorden, la camisa, la cara de concentración, el menú en el que lleva rato), "
    "con ingenio y cariño, nunca con crueldad. Nada de política, religión, físico ni cosas que ofendan de verdad. "
    "Español boricua natural, máximo 1 frase, sin saludos, sin hashtags, sin markdown, máximo 1 emoji. "
    "Reacciona específicamente a lo que se ve en pantalla y no repitas la misma broma de siempre."
)

VISION_INTERVAL = 600


async def bot_vision_comment(room: Room, channel: str):
    b64 = await fetch_thumb_b64(channel)
    if not b64:
        return
    try:
        comment = await gemini_vision(VISION_SYSTEM, "¿Qué está pasando en el stream?", b64, max_tokens=60)
        if comment:
            await room.broadcast({"type": "message", "user": "CORILLO BOT", "text": comment, "ts": time.time(), "bot": True})
    except:
        pass


async def vision_loop(room: Room, channel: str):
    await asyncio.sleep(VISION_INTERVAL)
    while len(room.clients) > 0:
        live = await get_live()
        live_keys = {p["name"].removeprefix("live/") for p in live}
        if channel in live_keys and time.time() - room._last_bot_reply >= VISION_INTERVAL:
            await bot_vision_comment(room, channel)
        await asyncio.sleep(VISION_INTERVAL)


# ── Quick commands ────────────────────────────────────────────────
COMMANDS = {"!canal", "!config", "!crew", "!discord", "!instagram"}

async def handle_command(room: Room, channel: str, cmd: str) -> bool:
    """Handle ! commands. Returns True if a known command was handled."""
    key = cmd.strip().lower().split()[0]
    if key not in COMMANDS:
        return False

    if key == "!canal":
        name = STREAMER_NAMES.get(channel, channel.upper())
        live = await get_live()
        live_keys = {p["name"].removeprefix("live/") for p in live}
        if channel in live_keys:
            viewers = next((len(p.get("readers", [])) for p in live if p["name"].removeprefix("live/") == channel), 0)
            status = f"🟢 En vivo ahora ({viewers} viewer{'s' if viewers != 1 else ''})"
        else:
            status = "⚫ Offline"
        reply = f"{name} — {status} | corillo.live/{channel}/"

    elif key == "!crew":
        names = " · ".join(STREAMER_NAMES.values())
        reply = f"Crew de CORILLO: {names} — corillo.live"

    elif key == "!config":
        reply = "Guía de configuración OBS / Meld Studio → corillo.live/configuracion/"

    elif key == "!discord":
        reply = f"Discord de CORILLO: {DISCORD_URL}" if DISCORD_URL else "Todavía no tenemos Discord oficial. ¡Pronto!"

    elif key == "!instagram":
        reply = f"Instagram de CORILLO: {INSTAGRAM_URL}" if INSTAGRAM_URL else "Todavía no tenemos Instagram oficial. ¡Pronto!"

    await room.broadcast({
        "type": "message", "user": "CORILLO BOT",
        "text": reply, "ts": time.time(), "bot": True,
    })
    return True


# ── Greeter ───────────────────────────────────────────────────────
_prev_live: set = set()
_greeted_at: dict = {}
GREET_COOLDOWN = 7200


async def greet_streamer(room: Room, channel: str):
    live = await get_live()
    if channel not in {p["name"].removeprefix("live/") for p in live}:
        return
    name = STREAMER_NAMES.get(channel, channel.upper())
    try:
        greeting = await groq(SYSTEM, (
            f"{name} acaba de empezar su stream en CORILLO. "
            "Escríbele un saludo corto con sarcasmo cariñoso y humor, en español boricua, "
            "como parte del crew dándole la bienvenida (una pullita amistosa, nada ofensivo). "
            "1 frase máximo. Sin hashtags, sin markdown, máx 1 emoji."
        ), max_tokens=60)
    except:
        greeting = f"¡Wepa {name}, arriba el stream! 🔥"
    room._last_bot_reply = time.time()
    await room.broadcast({"type": "message", "user": "CORILLO BOT", "text": greeting, "ts": time.time(), "bot": True})


async def live_monitor():
    global _prev_live
    await asyncio.sleep(20)
    try:
        live = await get_live()
        _prev_live = {p["name"].removeprefix("live/") for p in live}
    except:
        pass
    while True:
        try:
            live = await get_live()
            current = {p["name"].removeprefix("live/") for p in live}
            for ch in current - _prev_live:
                now = time.time()
                if now - _greeted_at.get(ch, 0) > GREET_COOLDOWN:
                    _greeted_at[ch] = now
                    room = get_room(ch)
                    asyncio.create_task(greet_streamer(room, ch))
            _prev_live = current
        except:
            pass
        await asyncio.sleep(15)


@app.on_event("startup")
async def startup():
    global _http, _db
    _http = httpx.AsyncClient(timeout=8, limits=httpx.Limits(max_connections=20, max_keepalive_connections=5))
    _db = await aiosqlite.connect(DB_PATH)
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA synchronous=NORMAL")
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL, user TEXT NOT NULL,
            text TEXT NOT NULL, ts REAL NOT NULL, bot INTEGER NOT NULL DEFAULT 0
        )
    """)
    await _db.execute("CREATE INDEX IF NOT EXISTS idx_channel_ts ON messages(channel, ts)")
    await _db.commit()
    asyncio.create_task(live_monitor())


@app.on_event("shutdown")
async def shutdown():
    if _http: await _http.aclose()
    if _db:   await _db.close()
