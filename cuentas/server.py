"""
corillo-cuentas — registro de streamers desde el formulario de corillo.live/join/.
Crea la cuenta en PocketBase (active:false) y PocketBase manda el correo de verificación;
el hook pb_hooks/activate_on_verify.pb.js la activa al confirmar. Puerto 3003.
Antes se llamaba corillo-telegram: el flujo de solicitudes por bot de Telegram, los avisos
"en vivo" por Telegram/Stoat/Discord y la escritura en GitHub se quitaron el 30-oct-2026
(los avisos de Discord los dará el Corillo-Bot nuevo).
"""
import os, re, time, secrets
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

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

_register_rl: dict[str, list] = {}
REGISTER_RL_MAX    = 3
REGISTER_RL_WINDOW = 3600

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

RESERVED_HANDLES = {
    'join', 'register', 'verificar', 'assets', 'mediamtx-api', 'live', 'api',
    'static', 'admin', 'robots', 'sitemap', 'favicon', 'index', 'stream',
    'dual', 'multiplayer', 'configuracion', 'roadmap', 'dmca', 'legal',
    'streamer-pro', 'player', 'perfil', 'webrtc', 'chat-api', 'twitch-api',
    'katatonia', 'tea', 'mira_sanganooo', '404', 'elbala', 'marcos',
    'pataecabra', 'streamerpro', 'radblaster', 'elhermanoquiles', 'xxdur3xx',
    'kamikazepr',
    # rutas del sitio (una cuenta con ese nombre quedaría tapada por la página)
    'mercado', 'equipo', 'ofertas', 'noticias', 'discord', 'streamers', 'vods', 'reels',
    'faq', 'software', 'embed', 'overlay', 'que_es_corillo', 'rss',
}


class RegisterRequest(BaseModel):
    handle:    str
    nombre:    str
    email:     str
    password:  str
    contenido: str
    plataforma: str = ""
    mensaje:   str = ""
    hp:        str = ""


async def _pb_admin_token() -> str:
    r = await _http.post(
        f"{PB_URL}/api/collections/_superusers/auth-with-password",
        json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
    )
    r.raise_for_status()
    return r.json()["token"]


@app.on_event("startup")
async def startup():
    global _http
    _http = httpx.AsyncClient(timeout=10.0)


@app.on_event("shutdown")
async def shutdown():
    await _http.aclose()


@app.post("/register")
async def register(req: RegisterRequest, request: Request):
    if req.hp:
        return {"ok": True}
    ip = (request.headers.get("x-real-ip")
          or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else "unknown"))
    now = time.time()
    hits = [t for t in _register_rl.get(ip, []) if now - t < REGISTER_RL_WINDOW]
    if len(hits) >= REGISTER_RL_MAX:
        raise HTTPException(status_code=429, detail="Demasiados intentos. Intenta más tarde.")
    hits.append(now)
    _register_rl[ip] = hits

    handle = req.handle.strip().lower()
    if not re.match(r'^[a-z0-9_]{3,24}$', handle):
        raise HTTPException(status_code=400, detail="Handle inválido")
    if "__" in handle:
        raise HTTPException(status_code=400, detail="Evita guiones bajos dobles en el handle")
    if handle in RESERVED_HANDLES:
        raise HTTPException(status_code=400, detail="Este handle está reservado")
    if not req.nombre.strip() or not req.contenido.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="Faltan campos requeridos")
    # El correo va dentro de un filtro de PocketBase: sin comillas ni nada raro
    if not EMAIL_RE.match(req.email.strip()):
        raise HTTPException(status_code=400, detail="Correo inválido")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    try:
        token = await _pb_admin_token()
    except Exception:
        raise HTTPException(status_code=503, detail="Servicio no disponible, intenta más tarde")
    headers = {"Authorization": token}

    dup = await _http.get(
        f"{PB_URL}/api/collections/streamers/records",
        headers=headers,
        params={"filter": f'key="{handle}" || email="{req.email.strip()}"'},
    )
    if dup.status_code == 200 and dup.json().get("items"):
        existing = dup.json()["items"][0]
        if existing.get("key") == handle:
            raise HTTPException(status_code=409, detail="Ese handle ya está en uso")
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")

    color = STREAMER_COLORS[hash(handle) % len(STREAMER_COLORS)]
    bio = req.contenido.strip()[:100]
    if req.plataforma.strip():
        bio += f" · antes en {req.plataforma.strip()[:40]}"
    stream_key = secrets.token_urlsafe(24)

    create = await _http.post(
        f"{PB_URL}/api/collections/streamers/records",
        headers=headers,
        json={
            "email": req.email.strip()[:120],
            "password": req.password,
            "passwordConfirm": req.password,
            "key": handle,
            "display_name": req.nombre.strip()[:60].upper(),
            "bio": bio,
            "color": color,
            "stream_key": stream_key,
            "stream_key_full": f"{handle}?secret={stream_key}",
            "active": False,
            "emailVisibility": False,
            "verified": False,
        },
    )
    if create.status_code not in (200, 201):
        raise HTTPException(status_code=400, detail="No se pudo crear la cuenta. Revisa los datos e intenta de nuevo.")

    try:
        await _http.post(
            f"{PB_URL}/api/collections/streamers/request-verification",
            json={"email": req.email.strip()[:120]},
        )
    except Exception:
        pass

    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "ok"}
