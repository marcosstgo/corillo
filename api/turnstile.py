"""
Cloudflare Turnstile — verificación del lado del servidor (siteverify), como la especifica
Cloudflare (developers.cloudflare.com/turnstile/spin/prompt.md): se exige success, la acción
esperada del formulario y un hostname de la lista permitida. Los tokens son de un solo uso:
siteverify rechaza un token ya canjeado.

Variables: TURNSTILE_SECRET (secreta, en .env) y TURNSTILE_HOSTNAMES (hostnames del frontend,
separados por coma; en producción solo corillo.live, nunca localhost).
"""
import os
from typing import Optional

import httpx

SITEVERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _hostnames() -> set[str]:
    return {h.strip() for h in os.environ.get("TURNSTILE_HOSTNAMES", "").split(",") if h.strip()}


def resultado_valido(result: dict, accion: str, hostnames: set[str]) -> bool:
    return (result.get("success") is True
            and result.get("action") == accion
            and result.get("hostname") in hostnames)


async def verificar(http: httpx.AsyncClient, token: Optional[str], accion: str, ip: str = "") -> bool:
    """True solo si Cloudflare confirma el token para esta acción y un hostname permitido.
    Cualquier fallo (token ausente, red, respuesta rara) es False: se falla cerrado."""
    secret = os.environ.get("TURNSTILE_SECRET", "")
    hostnames = _hostnames()
    if not isinstance(token, str) or not token or len(token) > 2048 or not secret or not hostnames:
        return False
    data = {"secret": secret, "response": token}
    if ip:
        data["remoteip"] = ip
    try:
        r = await http.post(SITEVERIFY, data=data, timeout=10)
        if r.status_code != 200:
            return False
        return resultado_valido(r.json(), accion, hostnames)
    except (httpx.HTTPError, ValueError):
        return False
