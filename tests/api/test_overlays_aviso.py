"""Aviso de problemas con overlays (/overlays/reporte): Turnstile, honeypot, límite por IP y correo."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cli(monkeypatch):
    import server, overlays, turnstile, correo
    overlays._log.clear()
    enviados = []
    estado = {"ts": True, "correo": True}

    async def ver(http, token, accion, ip=""):
        enviados.append(("ts", accion))
        return estado["ts"] and token == "ok"

    async def env(http, para, asunto, texto, html_="", responder_a="", nombre_remitente=""):
        enviados.append(("correo", para, asunto, texto, responder_a))
        return estado["correo"]

    monkeypatch.setattr(turnstile, "verificar", ver)
    monkeypatch.setattr(correo, "enviar", env)
    return TestClient(server.app), enviados, estado


BASE = {"juego": "bf6", "que": "Dice API not responding", "enlace": "https://corillo.live/overlay/bf6/overlay.html?name=sgJohn&platform=xbox",
        "contacto": "yo@ejemplo.com", "token": "ok"}


def test_envia_correo_con_los_datos(cli):
    c, env, _ = cli
    r = c.post("/overlays/reporte", json=BASE)
    assert r.status_code == 200 and r.json()["ok"]
    correo = [e for e in env if e[0] == "correo"][0]
    assert correo[1] == "hello@marcossantiago.com"
    assert "Battlefield 6" in correo[2] and "API not responding" in correo[2]
    assert "sgJohn" in correo[3] and "yo@ejemplo.com" in correo[3]
    assert correo[4] == "yo@ejemplo.com"                      # responder_a si es correo
    assert ("ts", "overlay") in env


def test_contacto_discord_no_va_a_reply_to(cli):
    c, env, _ = cli
    c.post("/overlays/reporte", json=BASE | {"contacto": "sgjohn#1234"})
    assert [e for e in env if e[0] == "correo"][0][4] == ""


def test_honeypot_dice_ok_y_no_manda_nada(cli):
    c, env, _ = cli
    r = c.post("/overlays/reporte", json=BASE | {"web": "http://spam"})
    assert r.status_code == 200 and env == []


def test_sin_turnstile_valido_403(cli):
    c, env, estado = cli
    estado["ts"] = False
    r = c.post("/overlays/reporte", json=BASE)
    assert r.status_code == 403 and not [e for e in env if e[0] == "correo"]


def test_limite_por_ip(cli):
    c, env, _ = cli
    codigos = [c.post("/overlays/reporte", json=BASE).status_code for _ in range(6)]
    assert codigos == [200] * 5 + [429]
    assert len([e for e in env if e[0] == "correo"]) == 5


def test_fallo_de_correo_502(cli):
    c, _, estado = cli
    estado["correo"] = False
    assert c.post("/overlays/reporte", json=BASE).status_code == 502


@pytest.mark.parametrize("cambio", [{"que": "hey"}, {"que": "x" * 1001}, {"juego": "fortnite"}, {"contacto": "x" * 121}])
def test_validacion_422(cli, cambio):
    c, env, _ = cli
    assert c.post("/overlays/reporte", json=BASE | cambio).status_code == 422 and env == []
