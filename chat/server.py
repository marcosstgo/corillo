import os, time, json, asyncio, random, base64
import httpx, anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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

NAMES = [
    "Coqui","Pitirre","Manatí","Gandule","Sofrito","Tostón",
    "Colmado","Boricua","Mofongo","Platano","Lechón","Bacalao",
    "Chinchorro","Aguacate","Tembleque","Pernil","Añejo","Pilón",
    "BadBunny","Coquí","Chulería","Alcapurria","Bacalaíto",
    "Sorullito","AyBendito","Algarete","Bomba","Plena","Coquito",
]

class Msg(BaseModel):
    message: str

async def get_live():
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get("https://corillo.live/mediamtx-api/v3/paths/list")
            return [p for p in r.json().get("items", []) if p.get("ready")]
    except:
        return []

async def fetch_thumb_b64(channel: str) -> str | None:
    url = f"https://corillo.live/assets/thumbs/{channel}.jpg"
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(url)
            if r.status_code == 200:
                return base64.standard_b64encode(r.content).decode()
    except:
        pass
    return None

@app.get("/health")
def health():
    return {"status": "ok"}

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
    def __init__(self):
        self.clients: dict = {}    # websocket → username
        self.history: list = []    # últimos 50 mensajes
        self.last_msg: dict = {}   # websocket → timestamp último mensaje
        self._vision_task = None   # loop de comentarios espontáneos

    async def join(self, ws: WebSocket, requested: str = "") -> str:
        await ws.accept()
        if requested and 3 <= len(requested) <= 40 and ' ' not in requested:
            username = requested
        else:
            username = random.choice(NAMES) + "_" + str(random.randint(10, 99))
        self.clients[ws] = username
        self.last_msg[ws] = 0.0
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
        for ws in list(self.clients):
            try:
                await ws.send_json(msg)
            except:
                self.clients.pop(ws, None)

rooms: dict = {}

def get_room(channel: str) -> Room:
    if channel not in rooms:
        rooms[channel] = Room()
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

async def vision_loop(room: Room, channel: str):
    # Espera inicial antes del primer comentario (2-3 min)
    await asyncio.sleep(random.uniform(120, 180))
    while len(room.clients) > 0:
        live = await get_live()
        live_keys = {p["name"].removeprefix("live/") for p in live}
        if channel in live_keys:
            await bot_vision_comment(room, channel)
        # Próximo comentario en 5-9 minutos
        await asyncio.sleep(random.uniform(300, 540))

# ── STREAMER GREETER ─────────────────────────────────────────────
STREAMER_NAMES = {
    "katatonia": "Katatonia",
    "tea": "Tea",
    "mira_sanganooo": "Mira_Sanganooo",
    "404": "404",
    "elbala": "Elbala",
    "marcos": "Marcos",
    "pataecabra": "Pataecabra",
    "streamerpro": "StreamerPro",
}

_prev_live: set = set()

async def greet_streamer(room: Room, channel: str):
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
    while True:
        try:
            live = await get_live()
            current_live = {p["name"].removeprefix("live/") for p in live}
            newly_live = current_live - _prev_live
            for ch in newly_live:
                room = get_room(ch)
                asyncio.create_task(greet_streamer(room, ch))
            _prev_live = current_live
        except:
            pass
        await asyncio.sleep(15)

@app.on_event("startup")
async def startup():
    asyncio.create_task(live_monitor())
