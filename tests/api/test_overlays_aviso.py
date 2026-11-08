"""Aviso de problemas con overlays (/overlays/reporte): Turnstile, honeypot, límite por IP y correo."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cli(monkeypatch):
    import server, overlays, turnstile, correo
    overlays._log.clear()
    enviados = []
    estado = {"ts": True, "correo": True, "discord": True}

    async def ver(http, token, accion, ip=""):
        enviados.append(("ts", accion))
        return estado["ts"] and token == "ok"

    async def env(http, para, asunto, texto, html_="", responder_a="", nombre_remitente=""):
        enviados.append(("correo", para, asunto, texto, responder_a))
        return estado["correo"]

    monkeypatch.setattr(turnstile, "verificar", ver)
    async def dm(texto):
        enviados.append(("discord", texto))
        return estado["discord"]

    monkeypatch.setattr(correo, "enviar", env)
    monkeypatch.setattr(overlays, "_discord", dm)
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


def test_discord_lleva_el_aviso(cli):
    c, env, _ = cli
    c.post("/overlays/reporte", json=BASE)
    dm = [e for e in env if e[0] == "discord"][0][1]
    assert "Battlefield 6" in dm and "sgJohn" in dm and "API not responding" in dm


def test_basta_uno_de_los_dos(cli):
    c, _, estado = cli
    estado["correo"] = False                       # hoy en el VPS no hay Mailgun
    assert c.post("/overlays/reporte", json=BASE).status_code == 200
    estado["discord"], estado["correo"] = False, True
    assert c.post("/overlays/reporte", json=BASE).status_code == 200


def test_sin_discord_ni_correo_502(cli):
    c, _, estado = cli
    estado["correo"] = estado["discord"] = False
    assert c.post("/overlays/reporte", json=BASE).status_code == 502


def test_discord_real_sin_avisar_py_es_false(monkeypatch):
    import asyncio, overlays
    monkeypatch.setattr(overlays, "AVISAR", "/no/existe/avisar.py")
    assert asyncio.run(overlays._discord("hola")) is False


def test_discord_real_con_script_falso(monkeypatch, tmp_path):
    import asyncio, overlays
    ok = tmp_path / "ok.py"; ok.write_text("import sys; open(sys.argv[0]+'.txt','w').write(sys.stdin.read())")
    malo = tmp_path / "malo.py"; malo.write_text("import sys; sys.exit(1)")
    monkeypatch.setattr(overlays, "AVISAR", str(ok))
    assert asyncio.run(overlays._discord("hola sgJohn")) is True
    assert (tmp_path / "ok.py.txt").read_text() == "hola sgJohn"
    monkeypatch.setattr(overlays, "AVISAR", str(malo))
    assert asyncio.run(overlays._discord("x")) is False


@pytest.mark.parametrize("cambio", [{"que": "hey"}, {"que": "x" * 1001}, {"juego": "fortnite"}, {"contacto": "x" * 121}])
def test_validacion_422(cli, cambio):
    c, env, _ = cli
    assert c.post("/overlays/reporte", json=BASE | cambio).status_code == 422 and env == []
