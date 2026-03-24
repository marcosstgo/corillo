"""
corillo-telegram — Telegram webhook, aprobación de streamers, notificaciones en vivo, /join.
Puerto 3003. Independiente del bot de chat.
"""
import os, re, time, json, asyncio, random, base64, secrets
import httpx, aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

load_dotenv()

MEDIAMTX_HOST  = os.environ.get("MEDIAMTX_HOST", "https://corillo.live/mediamtx-api")
DB_PATH        = os.environ.get("DB_PATH", "/home/corillo-adm/corillo-bot/chat.db")
ADMIN_TOKEN    = os.environ.get("ADMIN_TOKEN", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO    = os.environ.get("GITHUB_REPO", "marcosstgo/corillo")
GH_API         = "https://api.github.com"
PB_URL         = os.environ.get("PB_URL", "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS", "")

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
    "bambua": "AntonioLopez",
    "superman": "Superman",
    # AUTO_STREAMER_NAMES_END
}

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

_join_rl: dict[str, list] = {}
JOIN_RL_MAX    = 3
JOIN_RL_WINDOW = 3600


class JoinRequest(BaseModel):
    handle:    str
    nombre:    str
    email:     str
    contenido: str
    plataforma: str = ""
    mensaje:   str = ""
    hp:        str = ""


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


async def _tg(lines: list[str], handle: str = ""):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": "\n".join(lines), "parse_mode": "Markdown"}
        if handle:
            payload["reply_markup"] = {"inline_keyboard": [[
                {"text": "✅ Aprobar", "callback_data": f"approve:{handle}"},
                {"text": "❌ Rechazar", "callback_data": f"reject:{handle}"},
            ]]}
        await _http.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload)
    except:
        pass


async def _gh_get(path: str) -> tuple[str, str]:
    r = await _http.get(
        f"{GH_API}/repos/{GITHUB_REPO}/contents/{path}",
        headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"},
    )
    data = r.json()
    return base64.b64decode(data["content"]).decode(), data["sha"]


async def _gh_put(path: str, content: str, sha: str | None, message: str):
    payload = {
        "message": message,
        "content": base64.standard_b64encode(content.encode()).decode(),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    await _http.put(
        f"{GH_API}/repos/{GITHUB_REPO}/contents/{path}",
        headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"},
        json=payload,
    )


async def pb_create_streamer(handle: str, nombre: str, email: str, color: str):
    if not PB_ADMIN_EMAIL or not PB_ADMIN_PASS or not email:
        return
    try:
        r = await _http.post(
            f"{PB_URL}/api/collections/_superusers/auth-with-password",
            json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
        )
        token = r.json()["token"]
        headers = {"Authorization": token}
        name_up = nombre.upper() if nombre else handle.upper()
        stream_key = secrets.token_urlsafe(24)
        pw = secrets.token_urlsafe(32)
        r = await _http.post(
            f"{PB_URL}/api/collections/streamers/records",
            headers=headers,
            json={
                "email": email, "password": pw, "passwordConfirm": pw,
                "key": handle, "display_name": name_up, "color": color,
                "stream_key": stream_key,
                "stream_key_full": f"{handle}?secret={stream_key}",
                "active": True,
                "emailVisibility": False, "verified": True,
            },
        )
        if r.status_code not in (200, 201):
            r2 = await _http.get(
                f"{PB_URL}/api/collections/streamers/records",
                headers=headers, params={"filter": f'key="{handle}"'},
            )
            items = r2.json().get("items", [])
            if items:
                await _http.patch(
                    f"{PB_URL}/api/collections/streamers/records/{items[0]['id']}",
                    headers=headers, json={"email": email, "active": True},
                )
        await _http.post(
            f"{PB_URL}/api/collections/streamers/request-password-reset",
            json={"email": email},
        )
    except Exception as e:
        await _tg([f"⚠️ Pocketbase: no se pudo crear cuenta para @{handle}: {e}"])


async def auto_create_streamer(handle: str, nombre: str, contenido: str, email: str = ""):
    if not GITHUB_TOKEN:
        return
    try:
        color   = STREAMER_COLORS[hash(handle) % len(STREAMER_COLORS)]
        ava     = (nombre[0] if nombre else handle[0]).upper()
        name_up = nombre.upper() if nombre else handle.upper()
        sub     = contenido[:50] if contenido else "Gaming · CORILLO"

        # 1 — streamers.js
        js, js_sha = await _gh_get("assets/streamers.js")
        new_entry = (
            f"  {{ key:'{handle}', name:'{name_up}', "
            f"sub:'{sub}', ava:'{ava}', color:'{color}', host:false }},"
        )
        if "soon:true" in js:
            import re as _re
            js = _re.sub(r'\{[ \t]*key:null,', f"{new_entry}\n{{ key:null,", js, count=1)
        else:
            js = js.rstrip().rstrip("]").rstrip() + f"\n{new_entry}\n];\n"
        await _gh_put("assets/streamers.js", js, js_sha, f"feat: add streamer {handle} [auto]")

        # 2 — STREAMER_NAMES en telegram/server.py (self-update)
        py, py_sha = await _gh_get("telegram/server.py")
        name_fmt = nombre.title().replace(" ", "") if nombre else handle.title()
        sentinel = "# AUTO_STREAMER_" + "NAMES_END"
        py = py.replace(sentinel, f'"{handle}": "{name_fmt}",\n    {sentinel}')
        await _gh_put("telegram/server.py", py, py_sha, f"feat: add {handle} to STREAMER_NAMES [auto]")

        # Crear cuenta PB
        await pb_create_streamer(handle, nombre, email, color)

        pb_note = f" · email enviado a {email}" if email else ""
        await _tg([f"🚀 Canal @{handle} creado — deploy en curso (~1 min){pb_note}"])

    except Exception as e:
        await _tg([f"❌ Error creando @{handle}: {e}"])


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    cb = data.get("callback_query")
    if not cb:
        return {"ok": True}
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


@app.post("/join")
async def submit_join(req: JoinRequest, request: Request):
    if req.hp:
        return {"ok": True}
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

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        lines = [f"📥 *Nueva solicitud — @{handle}*",
                 f"Nombre: {req.nombre.strip()[:60]}",
                 f"Email: {req.email.strip()[:120]}",
                 f"Contenido: {req.contenido.strip()[:120]}"]
        if req.plataforma.strip():
            lines.append(f"Plataforma: {req.plataforma.strip()[:60]}")
        if req.mensaje.strip():
            lines.append(f"Mensaje: {req.mensaje.strip()[:200]}")
        asyncio.create_task(_tg(lines, handle=handle))
    return {"ok": True}


@app.get("/admin/requests")
async def admin_requests(token: str = ""):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403)
    _db.row_factory = aiosqlite.Row
    async with _db.execute(
        "SELECT id, handle, nombre, contenido, plataforma, mensaje, ts, status "
        "FROM join_requests ORDER BY ts DESC"
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Notificaciones en vivo ────────────────────────────────────────
_prev_live: set = set()
_notified_at: dict = {}
NOTIFY_COOLDOWN = 7200  # 2 horas


async def live_monitor():
    global _prev_live
    await asyncio.sleep(25)
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
                if now - _notified_at.get(ch, 0) > NOTIFY_COOLDOWN:
                    _notified_at[ch] = now
                    name = STREAMER_NAMES.get(ch, ch.upper())
                    asyncio.create_task(_tg([f"🔴 *{name} está en vivo*", f"corillo.live/{ch}"]))
            _prev_live = current
        except:
            pass
        await asyncio.sleep(15)


@app.on_event("startup")
async def startup():
    global _http, _db
    _http = httpx.AsyncClient(timeout=8, limits=httpx.Limits(max_connections=10, max_keepalive_connections=3))
    _db = await aiosqlite.connect(DB_PATH)
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA synchronous=NORMAL")
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS join_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            handle TEXT NOT NULL, nombre TEXT NOT NULL, email TEXT DEFAULT '',
            contenido TEXT NOT NULL, plataforma TEXT DEFAULT '', mensaje TEXT DEFAULT '',
            ts REAL NOT NULL, status TEXT DEFAULT 'pending'
        )
    """)
    await _db.commit()
    if TELEGRAM_TOKEN:
        try:
            await _http.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                json={"url": "https://corillo.live/chat-api/telegram-webhook",
                      "allowed_updates": ["callback_query"]},
            )
        except:
            pass
    asyncio.create_task(live_monitor())


@app.on_event("shutdown")
async def shutdown():
    if _http: await _http.aclose()
    if _db:   await _db.close()
