"""
Mercado de equipo usado (/api/mercado/*) — lo monta server.py con include_router.

Todo pasa por aquí: las colecciones mercado_* de PocketBase tienen todas sus reglas en null
(solo superusuario), así que el navegador no puede leerlas ni escribirlas directo. Esta capa
valida, aplica límites, procesa las fotos (WebP sin EXIF) y nunca devuelve datos privados
(correo del vendedor, WhatsApp) en los listados.

La lógica de filtros, orden y validación son funciones puras (sin red) para poder probarlas.
"""
import asyncio, io, json, math, os, re, secrets, time, unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable, Literal, Optional

import httpx
from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator

import correo
import turnstile

PB_URL = os.environ.get("PB_URL", "https://pb.corillo.live")
REPO = Path(os.environ.get("CORILLO_REPO", "/var/www/stream"))
ADMINS = {k.strip() for k in os.environ.get("MERCADO_ADMINS", "").split(",") if k.strip()}
AVISO_EMAIL = os.environ.get("MERCADO_AVISO_EMAIL", "hello@marcossantiago.com")   # aviso de cada anuncio nuevo
SITIO = os.environ.get("CORILLO_SITIO", "https://corillo.live")

MAX_ACTIVOS = int(os.environ.get("MERCADO_MAX_ACTIVOS", "15"))   # anuncios no vendidos por vendedor
MAX_CREA_HORA = int(os.environ.get("MERCADO_MAX_CREA_HORA", "5"))
MAX_FOTOS = 10
DIAS_VENDIDO_VISIBLE = 14
POR_PAGINA = 24

CONDICIONES = ("nuevo", "como-nuevo", "buen-estado", "para-piezas")
ENTREGAS = ("persona", "envio", "ambos")
ESTADOS = ("disponible", "reservado", "vendido")

router = APIRouter(prefix="/mercado")

# server.py inyecta su cliente HTTP y su token de superusuario (un solo pool de conexiones).
_get_http: Callable[[], httpx.AsyncClient] = lambda: None  # type: ignore
_admin_token: Callable[[], Awaitable[str]] = None  # type: ignore


_olvidar_token: Callable[[], None] = lambda: None


def bind(get_http, admin_token, olvidar_token=None):
    global _get_http, _admin_token, _olvidar_token
    _get_http, _admin_token = get_http, admin_token
    if olvidar_token:
        _olvidar_token = olvidar_token


# ── Datos compartidos con el frontend (una sola fuente) ─────────────────────
def _cargar(nombre: str):
    return json.loads((REPO / "src" / "data" / nombre).read_text(encoding="utf-8"))

CATEGORIAS = {c["slug"]: c for c in _cargar("categorias.json")}
MUNICIPIOS = {m["slug"]: m for m in _cargar("municipios.json")}


# ── Funciones puras ─────────────────────────────────────────────────────────
def normalizar(s: str) -> str:
    """minúsculas y sin acentos: 'Micrófono' y 'microfono' casan."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def distancia_km(a: str, b: str) -> float:
    """Distancia entre los centros de dos municipios (haversine)."""
    ma, mb = MUNICIPIOS.get(a), MUNICIPIOS.get(b)
    if not ma or not mb:
        return float("inf")
    la1, lo1, la2, lo2 = map(math.radians, (ma["lat"], ma["lng"], mb["lat"], mb["lng"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _fecha(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace(" ", "T").replace("Z", "+00:00"))
    except ValueError:
        return None


def es_publico(a: dict, ahora: Optional[datetime] = None) -> bool:
    """Visible para cualquiera: no oculto por moderación, no pausado, y si está vendido,
    solo durante DIAS_VENDIDO_VISIBLE días."""
    if a.get("moderacion") != "visible" or a.get("pausado"):
        return False
    if a.get("estado") == "vendido":
        v = _fecha(a.get("vendido_at", ""))
        ahora = ahora or datetime.now(timezone.utc)
        return bool(v) and ahora - v <= timedelta(days=DIAS_VENDIDO_VISIBLE)
    return True


class Filtros(BaseModel):
    q: str = ""
    categoria: str = ""
    subcategoria: str = ""
    pueblo: str = ""
    precio_min: Optional[float] = None
    precio_max: Optional[float] = None
    condicion: str = ""        # uno o varios separados por coma
    entrega: str = ""          # persona | envio (un anuncio "ambos" casa con los dos)
    orden: Literal["recientes", "precio_asc", "precio_desc", "cercania"] = "recientes"
    cerca: str = ""            # municipio de referencia para orden=cercania
    vendidos: bool = True      # incluir los vendidos recientes (van al final)
    pagina: int = Field(1, ge=1, le=500)


def filtrar(anuncios: list[dict], f: Filtros) -> list[dict]:
    """Aplica filtros y orden a anuncios YA públicos. Los vendidos siempre van al final."""
    terms = normalizar(f.q).split()
    conds = {c for c in f.condicion.split(",") if c}
    out = []
    for a in anuncios:
        if f.categoria and a.get("categoria") != f.categoria:
            continue
        if f.subcategoria and a.get("subcategoria") != f.subcategoria:
            continue
        if f.pueblo and a.get("pueblo") != f.pueblo:
            continue
        precio = a.get("precio") or 0
        if f.precio_min is not None and precio < f.precio_min:
            continue
        if f.precio_max is not None and precio > f.precio_max:
            continue
        if conds and a.get("condicion") not in conds:
            continue
        if f.entrega and a.get("entrega") not in (f.entrega, "ambos"):
            continue
        if not f.vendidos and a.get("estado") == "vendido":
            continue
        if terms:
            hay = normalizar(" ".join(str(a.get(k) or "") for k in ("titulo", "marca", "modelo", "descripcion")))
            if not all(t in hay for t in terms):
                continue
        out.append(a)

    if f.orden == "precio_asc":
        out.sort(key=lambda a: a.get("precio") or 0)
    elif f.orden == "precio_desc":
        out.sort(key=lambda a: -(a.get("precio") or 0))
    elif f.orden == "cercania" and f.cerca in MUNICIPIOS:
        out.sort(key=lambda a: (distancia_km(f.cerca, a.get("pueblo", "")), _neg_fecha(a)))
    else:
        out.sort(key=_neg_fecha)
    # sort estable: los vendidos bajan sin perder el orden elegido
    out.sort(key=lambda a: a.get("estado") == "vendido")
    return out


def _neg_fecha(a: dict) -> float:
    d = _fecha(a.get("created", ""))
    return -(d.timestamp() if d else 0)


def normalizar_whatsapp(v: str) -> str:
    """Acepta 787-555-1234, (939) 555 1234, +1 787…; guarda 10 dígitos. '' si viene vacío."""
    d = re.sub(r"\D", "", v or "")
    if not d:
        return ""
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) != 10:
        raise ValueError("El WhatsApp debe tener 10 dígitos (por ejemplo 787-555-1234).")
    return d


def _lista(v, campo: str) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list):
        raise ValueError(f"{campo}: debe ser una lista")
    items = [str(x).strip()[:120] for x in v if str(x).strip()]
    if len(items) > 25:
        raise ValueError(f"{campo}: máximo 25 renglones")
    return items


class AnuncioIn(BaseModel):
    """Lo que el vendedor puede mandar. estado/moderación/reportes/vendedor NO están aquí:
    los decide el servidor."""
    titulo: str = Field(..., min_length=5, max_length=90)
    categoria: str
    subcategoria: str = ""
    marca: str = Field("", max_length=60)
    modelo: str = Field("", max_length=80)
    condicion: Literal[CONDICIONES]  # type: ignore[valid-type]
    precio: float = Field(..., ge=0, le=100000)
    negociable: bool = False
    descripcion: str = Field("", max_length=3000)
    incluye: list[str] = []
    falta: list[str] = []
    pueblo: str
    entrega: Literal[ENTREGAS]  # type: ignore[valid-type]
    whatsapp: str = ""

    @field_validator("titulo", "marca", "modelo", "descripcion", mode="before")
    @classmethod
    def _strip(cls, v):
        return (v or "").strip() if isinstance(v, str) or v is None else v

    @field_validator("precio")
    @classmethod
    def _centavos(cls, v):
        return round(v, 2)

    @field_validator("categoria")
    @classmethod
    def _cat(cls, v):
        if v not in CATEGORIAS:
            raise ValueError("Categoría no válida")
        return v

    @field_validator("pueblo")
    @classmethod
    def _pueblo(cls, v):
        if v not in MUNICIPIOS:
            raise ValueError("Pueblo no válido")
        return v

    @field_validator("incluye", "falta", mode="before")
    @classmethod
    def _listas(cls, v, info):
        return _lista(v, info.field_name)

    @field_validator("whatsapp", mode="before")
    @classmethod
    def _wa(cls, v):
        return normalizar_whatsapp(v or "")

    def model_post_init(self, _):
        subs = {s["slug"] for s in CATEGORIAS[self.categoria]["sub"]}
        if self.subcategoria and self.subcategoria not in subs:
            raise ValueError("Subcategoría no válida para esa categoría")


class AnuncioPatch(AnuncioIn):
    """Edición: todo opcional."""
    titulo: Optional[str] = Field(None, min_length=5, max_length=90)  # type: ignore[assignment]
    categoria: Optional[str] = None  # type: ignore[assignment]
    condicion: Optional[Literal[CONDICIONES]] = None  # type: ignore
    precio: Optional[float] = Field(None, ge=0, le=100000)  # type: ignore[assignment]
    negociable: Optional[bool] = None  # type: ignore[assignment]
    pueblo: Optional[str] = None  # type: ignore[assignment]
    entrega: Optional[Literal[ENTREGAS]] = None  # type: ignore
    incluye: Optional[list[str]] = None  # type: ignore[assignment]
    falta: Optional[list[str]] = None  # type: ignore[assignment]
    whatsapp: Optional[str] = None  # type: ignore[assignment]

    @field_validator("categoria")
    @classmethod
    def _cat(cls, v):
        if v is not None and v not in CATEGORIAS:
            raise ValueError("Categoría no válida")
        return v

    @field_validator("pueblo")
    @classmethod
    def _pueblo(cls, v):
        if v is not None and v not in MUNICIPIOS:
            raise ValueError("Pueblo no válido")
        return v

    @field_validator("whatsapp", mode="before")
    @classmethod
    def _wa(cls, v):
        return None if v is None else normalizar_whatsapp(v)

    def model_post_init(self, _):
        pass  # la subcategoría se valida contra la categoría final en el endpoint


def transicion_estado(actual: str, nuevo: str, ahora: datetime) -> dict:
    """Cambios de estado permitidos. Cualquiera ↔ cualquiera (un trato se puede caer),
    pero la fecha de venta se fija al pasar a vendido y se borra al salir de vendido."""
    if nuevo not in ESTADOS:
        raise ValueError("Estado no válido")
    cambios = {"estado": nuevo}
    if nuevo == "vendido" and actual != "vendido":
        cambios["vendido_at"] = ahora.strftime("%Y-%m-%d %H:%M:%S.000Z")
    elif nuevo != "vendido":
        cambios["vendido_at"] = ""
    return cambios


# ── Fotos: WebP ≤1600 px, sin EXIF/GPS, rotación aplicada ─────────────────────
FOTO_MAX_BYTES = 15 * 1024 * 1024
FOTO_LADO = 1600


def procesar_foto(raw: bytes) -> bytes:
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 60_000_000  # rechaza "bombas" de descompresión
    if len(raw) > FOTO_MAX_BYTES:
        raise ValueError("La foto pesa más de 15 MB")
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:
        raise ValueError("El archivo no es una imagen válida")
    im = ImageOps.exif_transpose(im)          # aplica la orientación ANTES de botar el EXIF
    alfa = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    im = im.convert("RGBA" if alfa else "RGB")
    im.thumbnail((FOTO_LADO, FOTO_LADO), Image.LANCZOS)
    out = io.BytesIO()
    # Imagen nueva sin info: ni EXIF, ni XMP, ni GPS, ni comentarios.
    limpia = Image.new(im.mode, im.size)
    limpia.paste(im)
    limpia.save(out, "WEBP", quality=82, method=5)
    return out.getvalue()


def imagen_og(webp: bytes) -> bytes:
    """1200×630 JPEG (WhatsApp/Facebook no siempre muestran WebP en la vista previa)."""
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(webp)).convert("RGB")
    im = ImageOps.fit(im, (1200, 630), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    return out.getvalue()


# ── PocketBase ───────────────────────────────────────────────────────────────
COL = f"{PB_URL}/api/collections"
_cache_pub: dict = {"data": None, "ts": 0.0}
CACHE_TTL = 20
_crea_log: dict[str, list[float]] = {}


REBUILD_CMD = os.environ.get("MERCADO_REBUILD", str(REPO / "scripts" / "mercado-rebuild.sh"))
REBUILD_ESPERA = 20      # segundos: agrupa varios cambios seguidos en un solo build
_rebuild: dict = {"tarea": None}


def _invalidar():
    """Tras cualquier cambio: caché fuera y, en unos segundos, recompilar las páginas estáticas."""
    _cache_pub["data"] = None
    if not REBUILD_CMD:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _rebuild["tarea"] is None or _rebuild["tarea"].done():
        _rebuild["tarea"] = loop.create_task(_recompilar())


async def _recompilar():
    await asyncio.sleep(REBUILD_ESPERA)
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", REBUILD_CMD, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True)   # si la API se reinicia a mitad, el build termina igual
        await proc.wait()
    except Exception:
        pass


async def _pb(method: str, url: str, **kw) -> httpx.Response:
    token = await _admin_token()
    r = await _get_http().request(method, url, headers={"Authorization": token}, **kw)
    if r.status_code in (401, 403):     # token de superusuario vencido o revocado (PB lo trata como invitado): uno nuevo y reintento
        _olvidar_token()
        token = await _admin_token()
        r = await _get_http().request(method, url, headers={"Authorization": token}, **kw)
    return r


async def _vendedor(auth: Optional[str]) -> dict:
    """Cuenta autenticada (token de PocketBase de la colección streamers)."""
    if not auth:
        raise HTTPException(401, "Inicia sesión para continuar")
    r = await _get_http().post(f"{COL}/streamers/auth-refresh", headers={"Authorization": auth})
    if r.status_code != 200:
        raise HTTPException(401, "Tu sesión expiró. Vuelve a entrar.")
    rec = r.json().get("record", {})
    if not rec.get("verified"):
        raise HTTPException(403, "Confirma tu correo antes de publicar")
    return rec


def _es_admin(rec: dict) -> bool:
    return rec.get("key", "") in ADMINS


async def _bloqueado(tipo: str, valor: str) -> bool:
    r = await _pb("GET", f"{COL}/mercado_bloqueos/records",
                  params={"filter": f'tipo="{tipo}" && valor="{_esc(valor)}"', "perPage": 1, "fields": "id"})
    return bool(r.status_code == 200 and r.json().get("items"))


def _esc(v: str) -> str:
    return str(v).replace("\\", "").replace('"', "")


def _foto_url(a: dict, nombre: str) -> str:
    return f"{PB_URL}/api/files/{a['collectionId']}/{a['id']}/{nombre}"


def serializar(a: dict, privado: bool = False) -> dict:
    """Forma pública de un anuncio. `privado` añade lo que solo ve el dueño/admin."""
    v = (a.get("expand") or {}).get("vendedor") or {}
    streamer = bool(v.get("first_live_at")) and bool(v.get("active"))
    out = {
        "id": a["id"],
        "titulo": a["titulo"], "categoria": a["categoria"], "subcategoria": a.get("subcategoria", ""),
        "marca": a.get("marca", ""), "modelo": a.get("modelo", ""),
        "condicion": a["condicion"], "precio": a.get("precio") or 0, "negociable": bool(a.get("negociable")),
        "descripcion": a.get("descripcion", ""),
        "incluye": a.get("incluye") or [], "falta": a.get("falta") or [],
        "pueblo": a["pueblo"], "entrega": a["entrega"],
        "estado": a["estado"], "vendido_at": a.get("vendido_at", ""),
        "fotos": [_foto_url(a, f) for f in (a.get("fotos") or [])],
        "og": _foto_url(a, a["og"]) if a.get("og") else "",
        "tiene_whatsapp": bool(a.get("whatsapp")),
        "created": a.get("created", ""), "updated": a.get("updated", ""),
        "vendedor": {
            "key": v.get("key", ""), "nombre": v.get("display_name", "") or v.get("key", ""),
            "color": v.get("color", ""),
            "avatar": f"{PB_URL}/api/files/streamers/{v['id']}/{v['avatar']}" if v.get("avatar") else "",
            "streamer": streamer,
            "canal": f"/{v['key']}/" if streamer and v.get("key") else "",
        },
    }
    if privado:
        out.update({"pausado": bool(a.get("pausado")), "moderacion": a.get("moderacion"),
                    "motivo_oculto": a.get("motivo_oculto", ""), "reportes": a.get("reportes") or 0,
                    "whatsapp": a.get("whatsapp", "")})
    return out


VEND_FIELDS = "id,key,display_name,color,avatar,active,first_live_at"


async def _publicos() -> list[dict]:
    """Todos los anuncios públicos (caché corta). A la escala del Mercado caben en memoria,
    y así la búsqueda puede ignorar acentos y ordenar por cercanía."""
    now = time.time()
    if _cache_pub["data"] is not None and now - _cache_pub["ts"] < CACHE_TTL:
        return _cache_pub["data"]
    desde = (datetime.now(timezone.utc) - timedelta(days=DIAS_VENDIDO_VISIBLE)).strftime("%Y-%m-%d %H:%M:%S")
    r = await _pb("GET", f"{COL}/mercado_anuncios/records", params={
        "filter": f'moderacion="visible" && pausado=false && (estado!="vendido" || vendido_at>="{desde}")',
        "expand": "vendedor", "perPage": 1000, "sort": "-created",
    })
    r.raise_for_status()
    items = [a for a in r.json().get("items", [])
             if es_publico(a) and ((a.get("expand") or {}).get("vendedor") or {}).get("active")]
    data = [serializar(a) for a in items]
    _cache_pub.update({"data": data, "ts": now})
    return data


async def _obtener(aid: str) -> dict:
    if not re.fullmatch(r"[a-z0-9]{15}", aid or ""):
        raise HTTPException(404, "Anuncio no encontrado")
    r = await _pb("GET", f"{COL}/mercado_anuncios/records/{aid}", params={"expand": "vendedor"})
    if r.status_code != 200:
        raise HTTPException(404, "Anuncio no encontrado")
    return r.json()


async def _propio(aid: str, auth: Optional[str]) -> tuple[dict, dict]:
    yo = await _vendedor(auth)
    a = await _obtener(aid)
    if a["vendedor"] != yo["id"] and not _es_admin(yo):
        raise HTTPException(403, "Este anuncio no es tuyo")
    return a, yo


def _error_validacion(e: ValidationError) -> HTTPException:
    msgs = []
    for err in e.errors():
        campo = ".".join(str(x) for x in err.get("loc", []) if x != "__root__")
        msg = str(err.get("msg", "")).removeprefix("Value error, ")
        msgs.append(f"{campo}: {msg}" if campo else msg)
    return HTTPException(422, "; ".join(msgs))


def _limite_creacion(vid: str):
    ahora = time.time()
    log = [t for t in _crea_log.get(vid, []) if ahora - t < 3600]
    if len(log) >= MAX_CREA_HORA:
        raise HTTPException(429, "Publicaste varios anuncios seguidos. Espera un rato e intenta de nuevo.")
    log.append(ahora)
    _crea_log[vid] = log


async def _leer_fotos(files: list[UploadFile]) -> list[bytes]:
    if len(files) > MAX_FOTOS:
        raise HTTPException(422, f"Máximo {MAX_FOTOS} fotos por anuncio")
    out = []
    for f in files:
        raw = await f.read(FOTO_MAX_BYTES + 1)
        try:
            # Pillow es CPU puro: en un hilo aparte para no congelar la API (roster, avisos de directo…).
            out.append(await asyncio.to_thread(procesar_foto, raw))
        except ValueError as e:
            raise HTTPException(422, f"{f.filename or 'foto'}: {e}")
    return out


def _multipart(campos: dict, fotos: list[bytes], og: Optional[bytes]) -> tuple[dict, list]:
    data = {k: (json.dumps(v) if isinstance(v, (list, dict)) else ("true" if v is True else "false" if v is False else str(v)))
            for k, v in campos.items() if v is not None}
    files = [("fotos", (f"foto{i + 1}.webp", b, "image/webp")) for i, b in enumerate(fotos)]
    if og:
        files.append(("og", ("og.jpg", og, "image/jpeg")))
    return data, files


# ── Endpoints ───────────────────────────────────────────────────────────────
@router.get("/meta")
async def meta():
    """Categorías y municipios (el formulario y los filtros los usan)."""
    return {"categorias": list(CATEGORIAS.values()),
            "municipios": [{"slug": m["slug"], "nombre": m["nombre"]} for m in MUNICIPIOS.values()],
            "contacto": correo.configurado()}


@router.get("/anuncios")
async def listar(request: Request):
    try:
        f = Filtros(**dict(request.query_params))
    except ValidationError as e:
        raise _error_validacion(e)
    res = filtrar(await _publicos(), f)
    ini = (f.pagina - 1) * POR_PAGINA
    return {"total": len(res), "pagina": f.pagina, "por_pagina": POR_PAGINA, "items": res[ini:ini + POR_PAGINA]}


@router.get("/resumen")
async def resumen():
    """Conteo por categoría (para el build estático y los enlaces desde /equipo/)."""
    pub = await _publicos()
    por_cat: dict[str, int] = {}
    for a in pub:
        if a["estado"] != "vendido":
            por_cat[a["categoria"]] = por_cat.get(a["categoria"], 0) + 1
    return {"total": sum(por_cat.values()), "por_categoria": por_cat, "anuncios": pub}


@router.get("/anuncios/{aid}")
async def ver(aid: str, authorization: Optional[str] = Header(None)):
    a = await _obtener(aid)
    if es_publico(a) and ((a.get("expand") or {}).get("vendedor") or {}).get("active"):
        return serializar(a)
    # No público: solo su dueño o un admin (a los demás, 404: no revelamos que existe).
    if authorization:
        try:
            yo = await _vendedor(authorization)
            if a["vendedor"] == yo["id"] or _es_admin(yo):
                return serializar(a, privado=True)
        except HTTPException:
            pass
    raise HTTPException(404, "Anuncio no encontrado")


@router.get("/mis-anuncios")
async def mis_anuncios(authorization: Optional[str] = Header(None)):
    yo = await _vendedor(authorization)
    r = await _pb("GET", f"{COL}/mercado_anuncios/records", params={
        "filter": f'vendedor="{yo["id"]}"', "expand": "vendedor", "perPage": 200, "sort": "-created"})
    r.raise_for_status()
    return {"items": [serializar(a, privado=True) for a in r.json().get("items", [])],
            "max_activos": MAX_ACTIVOS}


@router.post("/anuncios", status_code=201)
async def crear(datos: str = Form(...), fotos: list[UploadFile] = File(default=[]),
                authorization: Optional[str] = Header(None)):
    yo = await _vendedor(authorization)
    if await _bloqueado("vendedor", yo["id"]):
        raise HTTPException(403, "Tu cuenta no puede publicar en el Mercado")
    try:
        inp = AnuncioIn(**json.loads(datos))
    except ValidationError as e:
        raise _error_validacion(e)
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e).removeprefix("Value error, "))
    if not fotos:
        raise HTTPException(422, "Añade al menos una foto")

    r = await _pb("GET", f"{COL}/mercado_anuncios/records", params={
        "filter": f'vendedor="{yo["id"]}" && estado!="vendido"', "perPage": 1, "fields": "id"})
    if r.json().get("totalItems", 0) >= MAX_ACTIVOS:
        raise HTTPException(409, f"Llegaste al máximo de {MAX_ACTIVOS} anuncios activos. Marca alguno como vendido o bórralo.")
    _limite_creacion(yo["id"])

    webps = await _leer_fotos(fotos)
    campos = inp.model_dump() | {"vendedor": yo["id"], "estado": "disponible", "moderacion": "visible",
                                  "pausado": False, "reportes": 0}
    data, files = _multipart(campos, webps, await asyncio.to_thread(imagen_og, webps[0]))
    r = await _pb("POST", f"{COL}/mercado_anuncios/records", data=data, files=files, params={"expand": "vendedor"})
    if r.status_code != 200:
        raise HTTPException(502, "No se pudo guardar el anuncio")
    _invalidar()
    nuevo = serializar(r.json(), privado=True)
    asyncio.create_task(_avisar_anuncio_nuevo(nuevo))
    return nuevo


async def _avisar_anuncio_nuevo(a: dict):
    """Correo a Marcos por cada anuncio nuevo (decisión 2026-09-24, mientras la comunidad es pequeña)."""
    try:
        url = f"{SITIO}/mercado/a/{a['id']}/"
        v = a["vendedor"]
        texto = (f"Anuncio nuevo en el Mercado:\n\n{a['titulo']}\n${a['precio']:,.2f}"
                 f"{' (negociable)' if a['negociable'] else ''} · {MUNICIPIOS.get(a['pueblo'], {}).get('nombre', a['pueblo'])}\n"
                 f"Vendedor: {v['nombre']} (@{v['key']}){' · streamer' if v['streamer'] else ''}\n\n{url}\n"
                 f"(La página tarda cerca de un minuto en existir mientras se recompila el sitio.)")
        await correo.enviar(_get_http(), AVISO_EMAIL, f"Mercado: {a['titulo'][:70]}", texto)
    except Exception:
        pass


@router.patch("/anuncios/{aid}")
async def editar(aid: str, request: Request, authorization: Optional[str] = Header(None)):
    a, _ = await _propio(aid, authorization)
    try:
        cambios = AnuncioPatch(**(await request.json())).model_dump(exclude_unset=True)
    except ValidationError as e:
        raise _error_validacion(e)
    cambios = {k: v for k, v in cambios.items() if v is not None or k == "whatsapp"}
    cat = cambios.get("categoria", a["categoria"])
    sub = cambios.get("subcategoria", a.get("subcategoria", "") if "categoria" not in cambios else "")
    if sub and sub not in {s["slug"] for s in CATEGORIAS[cat]["sub"]}:
        raise HTTPException(422, "subcategoria: Subcategoría no válida para esa categoría")
    cambios["subcategoria"] = sub
    r = await _pb("PATCH", f"{COL}/mercado_anuncios/records/{aid}", json=cambios, params={"expand": "vendedor"})
    if r.status_code != 200:
        raise HTTPException(502, "No se pudo guardar")
    _invalidar()
    return serializar(r.json(), privado=True)


@router.put("/anuncios/{aid}/fotos")
async def reemplazar_fotos(aid: str, fotos: list[UploadFile] = File(...), authorization: Optional[str] = Header(None)):
    """Reemplaza TODAS las fotos en el orden recibido (así también se reordenan)."""
    await _propio(aid, authorization)
    if not fotos:
        raise HTTPException(422, "Añade al menos una foto")
    webps = await _leer_fotos(fotos)
    data, files = _multipart({}, webps, await asyncio.to_thread(imagen_og, webps[0]))
    # En PocketBase, subir archivos con la clave 'fotos' (sin '+') SUSTITUYE los anteriores.
    r = await _pb("PATCH", f"{COL}/mercado_anuncios/records/{aid}", data=data, files=files, params={"expand": "vendedor"})
    if r.status_code != 200:
        raise HTTPException(502, "No se pudieron cambiar las fotos")
    _invalidar()
    return serializar(r.json(), privado=True)


@router.post("/anuncios/{aid}/orden-fotos")
async def ordenar_fotos(aid: str, request: Request, authorization: Optional[str] = Header(None)):
    """Reordena sin volver a subir: recibe la lista de nombres de archivo en el orden nuevo."""
    a, _ = await _propio(aid, authorization)
    orden = (await request.json()).get("fotos")
    actuales = a.get("fotos") or []
    if not isinstance(orden, list) or sorted(orden) != sorted(actuales):
        raise HTTPException(422, "La lista de fotos no coincide con las del anuncio")
    r = await _pb("PATCH", f"{COL}/mercado_anuncios/records/{aid}", json={"fotos": orden}, params={"expand": "vendedor"})
    if r.status_code != 200:
        raise HTTPException(502, "No se pudo reordenar")
    _invalidar()
    return serializar(r.json(), privado=True)


class EstadoIn(BaseModel):
    estado: Literal[ESTADOS]  # type: ignore[valid-type]


@router.post("/anuncios/{aid}/estado")
async def cambiar_estado(aid: str, body: EstadoIn, authorization: Optional[str] = Header(None)):
    a, _ = await _propio(aid, authorization)
    cambios = transicion_estado(a["estado"], body.estado, datetime.now(timezone.utc))
    r = await _pb("PATCH", f"{COL}/mercado_anuncios/records/{aid}", json=cambios, params={"expand": "vendedor"})
    if r.status_code != 200:
        raise HTTPException(502, "No se pudo cambiar el estado")
    _invalidar()
    return serializar(r.json(), privado=True)


class PausaIn(BaseModel):
    pausado: bool


@router.post("/anuncios/{aid}/pausa")
async def pausar(aid: str, body: PausaIn, authorization: Optional[str] = Header(None)):
    await _propio(aid, authorization)
    r = await _pb("PATCH", f"{COL}/mercado_anuncios/records/{aid}", json={"pausado": body.pausado}, params={"expand": "vendedor"})
    if r.status_code != 200:
        raise HTTPException(502, "No se pudo pausar")
    _invalidar()
    return serializar(r.json(), privado=True)


@router.delete("/anuncios/{aid}", status_code=204)
async def borrar(aid: str, authorization: Optional[str] = Header(None)):
    await _propio(aid, authorization)
    # Los mensajes quedan (sirven para moderar abuso); se desligan del anuncio al borrarlo.
    r = await _pb("DELETE", f"{COL}/mercado_anuncios/records/{aid}")
    if r.status_code not in (200, 204):
        raise HTTPException(502, "No se pudo borrar")
    _invalidar()


# ── Contacto, WhatsApp y reportes (visitantes sin cuenta, protegidos con Turnstile) ──
MAX_MSG_IP_HORA = 5          # mensajes por IP en una hora, a cualquier anuncio
MAX_MSG_IP_ANUNCIO_DIA = 2   # mensajes por IP al mismo anuncio en 24 h
MAX_WA_IP_HORA = 20
REPORTES_PARA_OCULTAR = 3
_wa_log: dict[str, list[float]] = {}


def ip_cliente(request: Request) -> str:
    """IP del visitante. Solo se cree la cabecera X-Real-IP si la petición viene de nginx (localhost);
    nginx la sobrescribe siempre, así que el navegador no puede falsificarla."""
    h = request.client.host if request.client else ""
    if h in ("127.0.0.1", "::1"):
        return request.headers.get("x-real-ip", "").strip() or h
    return h


def _ts(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%d %H:%M:%S")


async def _contar(col: str, filtro: str) -> int:
    r = await _pb("GET", f"{COL}/{col}/records", params={"filter": filtro, "perPage": 1, "fields": "id"})
    return r.json().get("totalItems", 0) if r.status_code == 200 else 0


async def _publico_o_404(aid: str) -> dict:
    a = await _obtener(aid)
    if not es_publico(a) or not ((a.get("expand") or {}).get("vendedor") or {}).get("active"):
        raise HTTPException(404, "Anuncio no encontrado")
    return a


class ContactoIn(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    mensaje: str = Field(..., min_length=10, max_length=2000)
    token: str = Field("", max_length=2048)       # cf-turnstile-response
    website: str = ""                             # honeypot: un humano nunca lo ve ni lo llena


@router.post("/anuncios/{aid}/contacto")
async def contactar(aid: str, request: Request):
    try:
        body = ContactoIn(**(await request.json()))
    except ValidationError as e:
        raise _error_validacion(e)
    except ValueError:
        raise HTTPException(422, "Datos inválidos")
    ok = {"ok": True, "mensaje": "Mensaje enviado. El vendedor te contestará a tu correo."}
    if body.website.strip():
        return ok                                   # bot: fingimos éxito y no hacemos nada
    ip = ip_cliente(request)
    if not await turnstile.verificar(_get_http(), body.token, "contacto", ip):
        raise HTTPException(403, "No pudimos confirmar que eres una persona. Recarga la página e intenta otra vez.")
    a = await _publico_o_404(aid)
    if a["estado"] == "vendido":
        raise HTTPException(409, "Este artículo ya se vendió.")
    if not correo.configurado():
        raise HTTPException(503, "El contacto todavía no está disponible. Intenta más tarde.")
    email = body.email.lower()
    if await _bloqueado("ip", ip) or await _bloqueado("email", email):
        raise HTTPException(403, "No puedes enviar mensajes en el Mercado.")
    if await _contar("mercado_mensajes", f'ip="{_esc(ip)}" && created>="{_ts(timedelta(hours=1))}"') >= MAX_MSG_IP_HORA:
        raise HTTPException(429, "Enviaste varios mensajes seguidos. Espera un rato e intenta de nuevo.")
    if await _contar("mercado_mensajes", f'ip="{_esc(ip)}" && anuncio="{aid}" && created>="{_ts(timedelta(days=1))}"') >= MAX_MSG_IP_ANUNCIO_DIA:
        raise HTTPException(429, "Ya le escribiste a este vendedor. Dale tiempo para contestar.")
    hilo = secrets.token_hex(12)
    nombre = _nombre_limpio(body.nombre)
    r = await _pb("POST", f"{COL}/mercado_mensajes/records", json={
        "anuncio": aid, "anuncio_titulo": a["titulo"], "vendedor": a["vendedor"],
        "nombre": nombre, "email": email, "mensaje": body.mensaje.strip(),
        "ip": ip, "enviado": False, "hilo": hilo, "respuestas": 0})
    if r.status_code != 200:
        raise HTTPException(502, "No se pudo enviar el mensaje. Intenta otra vez.")
    vend = (a.get("expand") or {}).get("vendedor") or {}
    url = f"{SITIO}/mercado/a/{aid}/"
    pie = ("Este mensaje te llegó a través del Mercado de CORILLO. Contesta a este correo y tu respuesta le "
           "llegará a la persona sin que vea tu dirección (ni tú la suya). CORILLO no participa en la venta: "
           "encuéntrense de día en un lugar público y no envíen dinero por adelantado.")
    parrafos = [f"{nombre} te escribió por tu anuncio \"{a['titulo']}\":", body.mensaje.strip(), url]
    enviado = await correo.enviar(
        _get_http(), vend.get("email", ""), f"Mercado: {nombre} pregunta por \"{a['titulo'][:60]}\"",
        "\n\n".join(parrafos) + "\n\n—\n" + pie, correo.html_simple(parrafos, pie),
        responder_a=correo.alias(hilo, "c"), nombre_remitente=nombre)
    if not enviado:
        raise HTTPException(502, "No se pudo enviar el mensaje. Intenta otra vez en unos minutos.")
    await _pb("PATCH", f"{COL}/mercado_mensajes/records/{r.json()['id']}", json={"enviado": True})
    return ok


def _nombre_limpio(n: str) -> str:
    """Va en el 'From' del correo: sin saltos de línea ni caracteres de cabecera."""
    return re.sub(r'[\r\n<>"@,;:\\]+', " ", n).strip()[:60] or "Alguien"


MAX_RESPUESTAS_HILO = 60


@router.post("/correo-entrante")
async def correo_entrante(request: Request):
    """Mailgun (Route r+*@mg.corillo.live → forward) manda aquí cada respuesta.
    Siempre contesta 200 salvo firma inválida, para que Mailgun no reintente correos descartados."""
    form = await request.form()
    if not correo.firma_valida(str(form.get("timestamp", "")), str(form.get("token", "")), str(form.get("signature", ""))):
        raise HTTPException(406, "firma inválida")
    destino = correo.leer_alias(str(form.get("recipient", "")))
    if not destino:
        return {"ok": False, "motivo": "alias"}
    hilo, lado = destino
    r = await _pb("GET", f"{COL}/mercado_mensajes/records", params={
        "filter": f'hilo="{hilo}"', "perPage": 1, "expand": "vendedor"})
    items = r.json().get("items", []) if r.status_code == 200 else []
    if not items:
        return {"ok": False, "motivo": "hilo"}
    m = items[0]
    vend = (m.get("expand") or {}).get("vendedor") or {}
    comprador, vendedor_email = m["email"].lower(), (vend.get("email") or "").lower()
    remitente = _direccion(str(form.get("sender", ""))) or _direccion(str(form.get("from", "")))
    # Solo la otra parte del hilo puede usar cada alias.
    esperado = vendedor_email if lado == "c" else comprador
    if not remitente or remitente != esperado:
        return {"ok": False, "motivo": "remitente"}
    if (m.get("respuestas") or 0) >= MAX_RESPUESTAS_HILO or await _bloqueado("email", remitente):
        return {"ok": False, "motivo": "limite"}
    texto = str(form.get("stripped-text") or form.get("body-plain") or "").strip()[:5000]
    if not texto:
        return {"ok": False, "motivo": "vacio"}
    para, responder, nombre = ((comprador, correo.alias(hilo, "v"), vend.get("display_name") or "El vendedor")
                               if lado == "c" else (vendedor_email, correo.alias(hilo, "c"), m["nombre"]))
    titulo = m.get("anuncio_titulo", "")
    pie = "Respuesta reenviada por el Mercado de CORILLO. Contesta a este correo para seguir la conversación; ninguno ve el correo del otro."
    ok = await correo.enviar(_get_http(), para, f"Re: Mercado: \"{titulo[:60]}\"", texto + "\n\n—\n" + pie,
                             correo.html_simple([texto], pie), responder_a=responder, nombre_remitente=_nombre_limpio(nombre))
    if ok:
        await _pb("PATCH", f"{COL}/mercado_mensajes/records/{m['id']}", json={
            "respuestas": (m.get("respuestas") or 0) + 1,
            "ultima_respuesta": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.000Z")})
    return {"ok": ok}


def _direccion(v: str) -> str:
    m = re.search(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+", v or "")
    return m.group(0).lower() if m else ""


class TokenIn(BaseModel):
    token: str = Field("", max_length=2048)


@router.post("/anuncios/{aid}/whatsapp")
async def ver_whatsapp(aid: str, body: TokenIn, request: Request):
    """El número nunca va en el HTML ni en los listados: solo sale aquí, tras Turnstile."""
    ip = ip_cliente(request)
    ahora = time.time()
    log = [t for t in _wa_log.get(ip, []) if ahora - t < 3600]
    if len(log) >= MAX_WA_IP_HORA:
        raise HTTPException(429, "Demasiadas consultas. Intenta más tarde.")
    if not await turnstile.verificar(_get_http(), body.token, "whatsapp", ip):
        raise HTTPException(403, "No pudimos confirmar que eres una persona. Recarga la página e intenta otra vez.")
    log.append(ahora)
    _wa_log[ip] = log
    a = await _publico_o_404(aid)
    if not a.get("whatsapp") or a["estado"] == "vendido":
        raise HTTPException(404, "Este anuncio no tiene WhatsApp")
    return {"whatsapp": a["whatsapp"]}


class ReporteIn(BaseModel):
    motivo: Literal["prohibido", "estafa", "spam", "ofensivo", "vendido", "otro"]
    detalle: str = Field("", max_length=500)
    token: str = Field("", max_length=2048)


@router.post("/anuncios/{aid}/reporte")
async def reportar(aid: str, body: ReporteIn, request: Request):
    ip = ip_cliente(request)
    if not await turnstile.verificar(_get_http(), body.token, "reporte", ip):
        raise HTTPException(403, "No pudimos confirmar que eres una persona. Recarga la página e intenta otra vez.")
    a = await _publico_o_404(aid)
    r = await _pb("POST", f"{COL}/mercado_reportes/records", json={
        "anuncio": aid, "motivo": body.motivo, "detalle": body.detalle.strip(), "ip": ip})
    if r.status_code != 200:
        # índice único (anuncio, ip): un reporte por persona y anuncio
        raise HTTPException(409, "Ya reportaste este anuncio. Lo vamos a revisar.")
    n = await _contar("mercado_reportes", f'anuncio="{aid}" && resuelto=false')
    cambios: dict = {"reportes": n}
    if n >= REPORTES_PARA_OCULTAR and a.get("moderacion") == "visible":
        cambios |= {"moderacion": "oculto", "motivo_oculto": f"Oculto automáticamente: {n} reportes"}
    await _pb("PATCH", f"{COL}/mercado_anuncios/records/{aid}", json=cambios)
    _invalidar()
    return {"ok": True, "mensaje": "Gracias. Vamos a revisar el anuncio."}


# ── Moderación (solo MERCADO_ADMINS) ─────────────────────────────────────────
async def _admin(auth: Optional[str]) -> dict:
    yo = await _vendedor(auth)
    if not _es_admin(yo):
        raise HTTPException(403, "Solo para admins del Mercado")
    return yo


@router.get("/yo")
async def yo(authorization: Optional[str] = Header(None)):
    v = await _vendedor(authorization)
    return {"key": v.get("key"), "nombre": v.get("display_name") or v.get("key"), "admin": _es_admin(v),
            "streamer": bool(v.get("first_live_at"))}


@router.get("/moderacion")
async def cola_moderacion(authorization: Optional[str] = Header(None)):
    await _admin(authorization)
    r = await _pb("GET", f"{COL}/mercado_anuncios/records", params={
        "filter": 'moderacion="oculto" || reportes>0', "expand": "vendedor", "perPage": 200, "sort": "-reportes,-updated"})
    pendientes = [serializar(a, privado=True) for a in r.json().get("items", [])]
    ids = [a["id"] for a in pendientes]
    reportes: dict[str, list] = {}
    if ids:
        filtro = "resuelto=false && (" + " || ".join(f'anuncio="{i}"' for i in ids[:100]) + ")"
        rr = await _pb("GET", f"{COL}/mercado_reportes/records", params={"filter": filtro, "perPage": 500, "sort": "-created"})
        for rep in rr.json().get("items", []):
            reportes.setdefault(rep["anuncio"], []).append({"motivo": rep["motivo"], "detalle": rep.get("detalle", ""), "created": rep["created"]})
    for a in pendientes:
        a["lista_reportes"] = reportes.get(a["id"], [])
    rec = await _pb("GET", f"{COL}/mercado_anuncios/records", params={"expand": "vendedor", "perPage": 30, "sort": "-created"})
    return {"pendientes": pendientes, "recientes": [serializar(a, privado=True) for a in rec.json().get("items", [])]}


class ModeracionIn(BaseModel):
    accion: Literal["aprobar", "ocultar", "banear"]
    motivo: str = Field("", max_length=300)


@router.post("/moderacion/{aid}")
async def moderar(aid: str, body: ModeracionIn, authorization: Optional[str] = Header(None)):
    yo = await _admin(authorization)
    a = await _obtener(aid)
    if body.accion == "aprobar":
        await _pb("PATCH", f"{COL}/mercado_anuncios/records/{aid}", json={"moderacion": "visible", "motivo_oculto": "", "reportes": 0})
        rr = await _pb("GET", f"{COL}/mercado_reportes/records", params={"filter": f'anuncio="{aid}" && resuelto=false', "perPage": 500, "fields": "id"})
        for rep in rr.json().get("items", []):
            await _pb("PATCH", f"{COL}/mercado_reportes/records/{rep['id']}", json={"resuelto": True})
    elif body.accion == "ocultar":
        await _pb("PATCH", f"{COL}/mercado_anuncios/records/{aid}", json={
            "moderacion": "oculto", "motivo_oculto": body.motivo or f"Oculto por @{yo.get('key')}"})
    else:  # banear al vendedor: no puede publicar y todos sus anuncios se ocultan
        vid = a["vendedor"]
        if vid == yo["id"]:
            raise HTTPException(422, "No te puedes banear a ti mismo")
        await _pb("POST", f"{COL}/mercado_bloqueos/records", json={
            "tipo": "vendedor", "valor": vid, "motivo": body.motivo or f"Baneado por @{yo.get('key')} (anuncio {aid})"})
        rr = await _pb("GET", f"{COL}/mercado_anuncios/records", params={"filter": f'vendedor="{vid}"', "perPage": 500, "fields": "id"})
        for x in rr.json().get("items", []):
            await _pb("PATCH", f"{COL}/mercado_anuncios/records/{x['id']}", json={
                "moderacion": "oculto", "motivo_oculto": "Vendedor baneado del Mercado"})
    _invalidar()
    return serializar(await _obtener(aid), privado=True)


# ── Limpieza (cron diario, solo desde el propio servidor) ────────────────────
RETENCION_DIAS = 365   # prometido en /legal/ (Política de privacidad): mensajes y reportes se borran a los 12 meses


@router.post("/internal/limpieza")
async def limpieza(request: Request):
    if (request.client.host if request.client else "") not in ("127.0.0.1", "::1"):
        raise HTTPException(403)
    limite = _ts(timedelta(days=RETENCION_DIAS))
    borrados = {}
    for col in ("mercado_mensajes", "mercado_reportes"):
        n = 0
        while True:
            r = await _pb("GET", f"{COL}/{col}/records", params={"filter": f'created<"{limite}"', "perPage": 200, "fields": "id"})
            items = r.json().get("items", []) if r.status_code == 200 else []
            if not items:
                break
            for it in items:
                await _pb("DELETE", f"{COL}/{col}/records/{it['id']}")
                n += 1
        borrados[col] = n
    return borrados
