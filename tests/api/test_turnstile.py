"""Verificación de Turnstile: se exige success + acción + hostname permitido, y falla cerrado."""
import asyncio, json

import httpx
import pytest

import turnstile


def cliente(respuesta: dict | None, status=200, visto: list | None = None):
    def handler(req: httpx.Request):
        if visto is not None:
            visto.append(dict(x.split("=", 1) for x in req.content.decode().split("&")))
        if respuesta is None:
            raise httpx.ConnectError("sin red")
        return httpx.Response(status, json=respuesta)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("TURNSTILE_SECRET", "secreto-de-prueba")
    monkeypatch.setenv("TURNSTILE_HOSTNAMES", "corillo.live")


BUENA = {"success": True, "action": "contacto", "hostname": "corillo.live"}
v = lambda http, token="tok", accion="contacto", ip="1.2.3.4": asyncio.run(turnstile.verificar(http, token, accion, ip))


def test_acepta_solo_lo_correcto_y_manda_secret_y_ip():
    visto = []
    assert v(cliente(BUENA, visto=visto)) is True
    assert visto[0]["secret"] == "secreto-de-prueba" and visto[0]["response"] == "tok" and visto[0]["remoteip"] == "1.2.3.4"


@pytest.mark.parametrize("resp", [
    BUENA | {"success": False},
    BUENA | {"action": "reporte"},                  # token de otro formulario
    BUENA | {"hostname": "example.com"},            # token emitido en otro sitio (p. ej. llaves de prueba)
    BUENA | {"hostname": "localhost"},              # localhost nunca vale en producción
    {"success": False, "error-codes": ["timeout-or-duplicate"]},   # token reutilizado
])
def test_rechaza(resp):
    assert v(cliente(resp)) is False


def test_falla_cerrado():
    assert v(cliente(None)) is False                                 # sin red
    assert v(cliente(BUENA, status=500)) is False
    assert v(cliente(BUENA), token="") is False
    assert v(cliente(BUENA), token="x" * 2049) is False
    assert v(cliente(BUENA), token=None) is False


def test_sin_configurar_no_deja_pasar(monkeypatch):
    monkeypatch.setenv("TURNSTILE_SECRET", "")
    assert v(cliente(BUENA)) is False
    monkeypatch.setenv("TURNSTILE_SECRET", "s")
    monkeypatch.setenv("TURNSTILE_HOSTNAMES", "")
    assert v(cliente(BUENA)) is False
