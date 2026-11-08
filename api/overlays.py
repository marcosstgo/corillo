"""
Avisos de problemas con los overlays (/api/overlays/reporte) — lo monta server.py con include_router.

Los overlays corren dentro del OBS de cada streamer: si algo falla, Corillo no se entera.
El botón «Avísanos» de /overlay/ manda aquí lo que pasa y le llega a Marcos por DM de Discord
(avisar.py, con el token del Bochinchero) y, si Mailgun está configurado, también por correo.
Protegido con Turnstile (acción «overlay»), honeypot y un límite por IP.
"""
import asyncio, os, re, time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import correo
import turnstile
from mercado import ip_cliente

AVISO_EMAIL = os.environ.get("OVERLAYS_AVISO_EMAIL", os.environ.get("MERCADO_AVISO_EMAIL", "hello@marcossantiago.com"))
AVISAR = os.environ.get("AVISAR_PY", str(Path.home() / "avisar.py"))   # scripts/vps/avisar.py de corillo-server
POR_HORA = 5                      # avisos por IP por hora
_log: dict[str, list[float]] = {}
_http = None

router = APIRouter(prefix="/overlays")


def bind(get_http):
    global _http
    _http = get_http


def _limite(ip: str, ahora: float | None = None) -> bool:
    """True si la IP todavía puede mandar otro aviso esta hora (y lo cuenta)."""
    ahora = time.time() if ahora is None else ahora
    v = [t for t in _log.get(ip, []) if ahora - t < 3600]
    if len(v) >= POR_HORA:
        _log[ip] = v
        return False
    v.append(ahora)
    _log[ip] = v
    return True


def armar_correo(juego: str, que: str, enlace: str, contacto: str, ip: str) -> tuple[str, str, str]:
    """(asunto, texto, responder_a). responder_a solo si el contacto parece un correo."""
    nombres = {"bf6": "Battlefield 6", "wardogs": "WARDOGS", "otro": "Otro / no sé"}
    resumen = re.sub(r"\s+", " ", que).strip()
    asunto = f"Overlay ({nombres[juego]}): {resumen[:60]}{'…' if len(resumen) > 60 else ''}"
    texto = (f"Alguien avisó de un problema con un overlay.\n\n"
             f"Juego: {nombres[juego]}\n"
             f"Qué pasa:\n{que.strip()}\n\n"
             f"Enlace del overlay: {enlace.strip() or '(no lo puso)'}\n"
             f"Contacto: {contacto.strip() or '(no lo puso)'}\n"
             f"IP: {ip}\n")
    c = contacto.strip()
    responder_a = c if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", c) else ""
    return asunto, texto, responder_a


async def _discord(texto: str) -> bool:
    """DM a Marcos con avisar.py. False si no está o falla (nunca revienta la petición)."""
    if not os.path.isfile(AVISAR):
        return False
    try:
        p = await asyncio.create_subprocess_exec("python3", AVISAR, "dm", stdin=asyncio.subprocess.PIPE,
                                                 stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.wait_for(p.communicate(texto.encode()), timeout=30)
        return p.returncode == 0
    except Exception:
        return False


class AvisoIn(BaseModel):
    juego: Literal["bf6", "wardogs", "otro"] = "otro"
    que: str = Field(..., min_length=5, max_length=1000)
    enlace: str = Field("", max_length=500)
    contacto: str = Field("", max_length=120)
    web: str = Field("", max_length=200)          # honeypot: una persona nunca lo llena
    token: str = Field("", max_length=2048)       # cf-turnstile-response


@router.post("/reporte")
async def reportar(body: AvisoIn, request: Request):
    ip = ip_cliente(request)
    if body.web:                                   # bot: se le dice que sí y no se manda nada
        return {"ok": True}
    if not await turnstile.verificar(_http(), body.token, "overlay", ip):
        raise HTTPException(403, "No pudimos confirmar que eres una persona. Recarga la página e intenta otra vez.")
    if not _limite(ip):
        raise HTTPException(429, "Ya recibimos varios avisos tuyos. Intenta otra vez en un rato.")
    asunto, texto, responder_a = armar_correo(body.juego, body.que, body.enlace, body.contacto, ip)
    por_discord = await _discord(f"🛠️ **{asunto}**\n{texto}")
    por_correo = await correo.enviar(_http(), AVISO_EMAIL, asunto, texto, responder_a=responder_a)
    if not (por_discord or por_correo):
        raise HTTPException(502, "No se pudo enviar el aviso. Intenta otra vez en un rato.")
    return {"ok": True, "mensaje": "¡Gracias! Ya nos llegó. Lo vamos a revisar."}
