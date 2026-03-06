import os
import time
import httpx
import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI
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

# ── Digest cache (2 min) ──────────────────────────────────────────
_digest = {"text": "", "ts": 0}
DIGEST_TTL = 120

@app.get("/digest")
async def digest():
    if time.time() - _digest["ts"] < DIGEST_TTL and _digest["text"]:
        return {"digest": _digest["text"]}

    live = await get_live()

    if live:
        lines = "\n".join(
            f"- {p['name']}: {len(p.get('readers', []))} viewers" for p in live
        )
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
