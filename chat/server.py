"""
corillo-bot — Chat en vivo, IA, WebSocket.
Puerto 3001. Solo responsabilidad: chat.
"""
import os, time, json, asyncio, random, base64
import httpx, aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from system_prompt import SYSTEM

load_dotenv()

MEDIAMTX_HOST = os.environ.get("MEDIAMTX_HOST", "https://corillo.live/mediamtx-api")
THUMBS_HOST   = os.environ.get("THUMBS_HOST",   "https://corillo.live")
DB_PATH       = os.environ.get("DB_PATH", "/home/corillo-adm/corillo-bot/chat.db")

DISCORD_URL   = os.environ.get("DISCORD_URL",   "")
INSTAGRAM_URL = os.environ.get("INSTAGRAM_URL", "")

GROQ_API_KEY        = os.environ.get("GROQ_API_KEY",   "")
GROQ_MODEL          = os.environ.get("GROQ_MODEL",    "llama-3.3-70b-versatile")
GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "")
GEMINI_VISION_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")


async def groq(system: str, prompt: str, max_tokens: int = 150) -> str:
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": max_tokens,
    }
    r = await _http.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        timeout=30,
    )
    return r.json()["choices"][0]["message"]["content"].strip()


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

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://corillo.live", "http://localhost:8080"],
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


class Msg(BaseModel):
    message: str


async def get_live():
    now = time.time()
    if now - _live_cache["ts"] < LIVE_CACHE_TTL:
        return _live_cache["data"]
    try:
        r = await _http.get(f"{MEDIAMTX_HOST}/v3/paths/list")
        result = [p for p in r.json().get("items", []) if p.get("ready")]
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


@app.post("/message")
async def chat(body: Msg):
    live = await get_live()
    status = ("En vivo ahora:\n" + "\n".join(
        f"- {p['name']}: {len(p.get('readers', []))} viewers" for p in live
    )) if live else "Sin streams en vivo."
    reply = await groq(SYSTEM + f"\n\n{status}", body.message, max_tokens=512)
    return {"reply": reply}


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
    _digest["text"] = await groq(SYSTEM, prompt, max_tokens=80)
    _digest["ts"] = time.time()
    return {"digest": _digest["text"]}


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
        if requested and 3 <= len(requested) <= 40 and ' ' not in requested:
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
    room = get_room(channel)
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
    "Eres un viewer más del stream. Estás viendo una captura de pantalla del stream en vivo. "
    "Reacciona a lo que ves en la imagen con UN comentario MUY corto y casual en español, "
    "como lo haría alguien del crew boricua mirando el stream. "
    "Máximo 1 frase breve. Sin saludos, sin hashtags. Máximo 1 emoji si aplica. "
    "Reacciona específicamente a lo que se ve en pantalla."
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
            "Escríbele un saludo corto y entusiasta en español boricua, "
            "como parte del crew dándole la bienvenida. "
            "1 frase máximo. Sin hashtags, sin emojis (máx 1)."
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
