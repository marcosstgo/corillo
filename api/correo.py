"""
Correo del Mercado por la API HTTP de Mailgun (dominio mg.corillo.live).

Reenvío ciego en ambos sentidos: cada conversación ("hilo") tiene dos alias,
  r+<hilo>.c@mg.corillo.live  → le llega al COMPRADOR (lo usa el vendedor para contestar)
  r+<hilo>.v@mg.corillo.live  → le llega al VENDEDOR (lo usa el comprador)
Una Route de Mailgun manda lo que llegue a r+* a /api/mercado/correo-entrante, que verifica la
firma del webhook y reenvía. Ninguna de las partes ve el correo de la otra.

Variables: MAILGUN_API_KEY, MAILGUN_WEBHOOK_SIGNING_KEY, MAILGUN_DOMAIN (mg.corillo.live),
MAILGUN_API_BASE (https://api.mailgun.net; la de la UE es https://api.eu.mailgun.net).
"""
import hashlib, hmac, html, os, re, time
from typing import Optional

import httpx

DOMINIO = os.environ.get("MAILGUN_DOMAIN", "mg.corillo.live")
API_BASE = os.environ.get("MAILGUN_API_BASE", "https://api.mailgun.net")
REMITENTE = f"Mercado de CORILLO <noreply@{DOMINIO}>"
ALIAS_RE = re.compile(r"^r\+([a-z0-9]{16,40})\.([cv])@" + re.escape(DOMINIO) + r"$")
_tokens_vistos: dict[str, float] = {}


def configurado() -> bool:
    return bool(os.environ.get("MAILGUN_API_KEY"))


def alias(hilo: str, lado: str) -> str:
    """lado 'c' = le llega al comprador; 'v' = le llega al vendedor."""
    return f"r+{hilo}.{lado}@{DOMINIO}"


def leer_alias(direccion: str) -> Optional[tuple[str, str]]:
    m = ALIAS_RE.match((direccion or "").strip().lower())
    return (m.group(1), m.group(2)) if m else None


def firma_valida(timestamp: str, token: str, signature: str, ahora: Optional[float] = None) -> bool:
    """Firma de los webhooks de Mailgun: HMAC-SHA256(signing_key, timestamp+token).
    Rechaza firmas viejas (>15 min) y tokens repetidos (replay)."""
    key = os.environ.get("MAILGUN_WEBHOOK_SIGNING_KEY", "")
    if not key or not timestamp or not token or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    ahora = ahora or time.time()
    if abs(ahora - ts) > 900:
        return False
    esperado = hmac.new(key.encode(), f"{timestamp}{token}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(esperado, signature):
        return False
    for t, cuando in list(_tokens_vistos.items()):
        if ahora - cuando > 1800:
            del _tokens_vistos[t]
    if token in _tokens_vistos:
        return False
    _tokens_vistos[token] = ahora
    return True


def html_simple(parrafos: list[str], pie: str) -> str:
    cuerpo = "".join(f'<p style="margin:0 0 14px;line-height:1.55">{html.escape(p).replace(chr(10), "<br>")}</p>' for p in parrafos)
    return (f'<div style="font-family:Arial,sans-serif;font-size:15px;color:#10183a;max-width:560px">{cuerpo}'
            f'<p style="margin:22px 0 0;padding-top:12px;border-top:1px solid #dde;color:#667;font-size:12px;line-height:1.5">'
            f'{html.escape(pie)}</p></div>')


async def enviar(http: httpx.AsyncClient, para: str, asunto: str, texto: str, html_: str = "",
                 responder_a: str = "", nombre_remitente: str = "") -> bool:
    key = os.environ.get("MAILGUN_API_KEY", "")
    if not key:
        return False
    remitente = f"{nombre_remitente} vía CORILLO <noreply@{DOMINIO}>" if nombre_remitente else REMITENTE
    data = {"from": remitente, "to": para, "subject": asunto, "text": texto}
    if html_:
        data["html"] = html_
    if responder_a:
        data["h:Reply-To"] = responder_a
    try:
        r = await http.post(f"{API_BASE}/v3/{DOMINIO}/messages", auth=("api", key), data=data, timeout=15)
        return r.status_code == 200
    except httpx.HTTPError:
        return False
