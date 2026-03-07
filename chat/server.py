import os, time, json, asyncio, random
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

    async def join(self, ws: WebSocket) -> str:
        await ws.accept()
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
    username = await room.join(ws)

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
                asyncio.create_task(bot_reply(room, query))

    except WebSocketDisconnect:
        room.leave(ws)

async def bot_reply(room: Room, query: str):
    live = await get_live()
    status = ("En vivo:\n" + "\n".join(
        f"- {p['name']}: {len(p.get('readers', []))} viewers" for p in live
    )) if live else "Sin streams en vivo."
    try:
        res = await asyncio.to_thread(
            ac.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=SYSTEM + f"\n\n{status}",
            messages=[{"role": "user", "content": query}],
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
