"""Integración: la API real contra la PocketBase desechable (scripts/pb-test-server.sh).
Cubre crear, permisos, estados, pausa, filtros, privacidad y el canal oculto hasta el primer directo."""
import io, json, os, uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

PB = os.environ["PB_URL"]


def _pb_vivo() -> bool:
    try:
        return httpx.get(f"{PB}/api/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


# En CI la PocketBase desechable SIEMPRE está (si no, falla el paso anterior); en local se saltan.
pytestmark = pytest.mark.skipif(not _pb_vivo(), reason="PocketBase de pruebas no disponible (scripts/pb-test-server.sh)")


def _su() -> str:
    r = httpx.post(f"{PB}/api/collections/_superusers/auth-with-password",
                   json={"identity": os.environ["PB_ADMIN_EMAIL"], "password": os.environ["PB_ADMIN_PASS"]})
    return r.json()["token"]


def cuenta(key=None, verified=True, active=True, streamer=False) -> dict:
    key = key or "u" + uuid.uuid4().hex[:10]
    body = {"key": key, "display_name": key.upper(), "email": f"{key}@x.test", "password": "clave-segura-123",
            "passwordConfirm": "clave-segura-123", "verified": verified, "active": active,
            "first_live_at": "2026-01-01 00:00:00.000Z" if streamer else ""}
    r = httpx.post(f"{PB}/api/collections/streamers/records", json=body, headers={"Authorization": _su()})
    assert r.status_code == 200, r.text
    tok = httpx.post(f"{PB}/api/collections/streamers/auth-with-password",
                     json={"identity": body["email"], "password": body["password"]}).json().get("token", "")
    return {"id": r.json()["id"], "key": key, "h": {"Authorization": tok}}


def foto() -> bytes:
    out = io.BytesIO(); Image.new("RGB", (800, 600), (10, 60, 200)).save(out, "JPEG"); return out.getvalue()


TRIDENT = {
    "titulo": "MSI MEG Trident X2 – Base con i9-13900KF y pantalla HMI", "categoria": "pc",
    "subcategoria": "pc-completas", "condicion": "buen-estado", "precio": 400, "negociable": True,
    "incluye": ["Intel Core i9-13900KF", "Placa MSI Z790", "Chasis Trident X2 con HMI 2.0", "Wi-Fi 6E y red dual"],
    "falta": ["Tarjeta de video", "RAM DDR5", "SSD", "Fuente de poder", "Water cooler 280 mm"],
    "pueblo": "aibonito", "entrega": "persona", "whatsapp": "787-555-1234",
}


@pytest.fixture(scope="module")
def c():
    import server
    with TestClient(server.app) as cl:
        yield cl


def crear(c, u, **cambios):
    return c.post("/mercado/anuncios", headers=u["h"], data={"datos": json.dumps(TRIDENT | cambios)},
                  files=[("fotos", ("a.jpg", foto(), "image/jpeg")), ("fotos", ("b.jpg", foto(), "image/jpeg"))])


def test_crear_anuncio_completo_y_privacidad(c):
    u = cuenta()
    r = crear(c, u)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["estado"] == "disponible" and a["moderacion"] == "visible" and len(a["fotos"]) == 2
    assert a["fotos"][0].endswith(".webp") and a["og"].endswith(".jpg")
    assert a["vendedor"]["streamer"] is False and a["vendedor"]["canal"] == ""
    pub = c.get(f"/mercado/anuncios/{a['id']}").json()
    texto = json.dumps(pub)
    assert "7875551234" not in texto and "@x.test" not in texto and pub["tiene_whatsapp"] is True
    listado = json.dumps(c.get("/mercado/anuncios").json())
    assert "7875551234" not in listado and "@x.test" not in listado


def test_sin_sesion_o_sin_verificar_no_publica(c):
    r = c.post("/mercado/anuncios", data={"datos": json.dumps(TRIDENT)}, files=[("fotos", ("a.jpg", foto(), "image/jpeg"))])
    assert r.status_code == 401
    nv = cuenta(verified=False)
    assert crear(c, nv).status_code in (401, 403)


def test_validacion_backend(c):
    u = cuenta()
    assert crear(c, u, categoria="armas").status_code == 422
    assert crear(c, u, precio=-5).status_code == 422
    r = c.post("/mercado/anuncios", headers=u["h"], data={"datos": json.dumps(TRIDENT)})
    assert r.status_code == 422                                     # sin fotos
    r = c.post("/mercado/anuncios", headers=u["h"], data={"datos": json.dumps(TRIDENT)},
               files=[("fotos", ("x.jpg", b"no soy imagen", "image/jpeg"))])
    assert r.status_code == 422


def test_campos_del_servidor_se_ignoran(c):
    u = cuenta()
    a = crear(c, u, estado="vendido", moderacion="oculto", reportes=99).json()
    assert a["estado"] == "disponible" and a["moderacion"] == "visible" and a["reportes"] == 0


def test_solo_dueno_o_admin_editan(c):
    import mercado
    dueno, otro, admin = cuenta(), cuenta(), cuenta()
    mercado.ADMINS.add(admin["key"])
    aid = crear(c, dueno).json()["id"]
    assert c.patch(f"/mercado/anuncios/{aid}", headers=otro["h"], json={"precio": 1}).status_code == 403
    assert c.post(f"/mercado/anuncios/{aid}/estado", headers=otro["h"], json={"estado": "vendido"}).status_code == 403
    assert c.delete(f"/mercado/anuncios/{aid}", headers=otro["h"]).status_code == 403
    assert c.patch(f"/mercado/anuncios/{aid}", json={"precio": 1}).status_code == 401
    r = c.patch(f"/mercado/anuncios/{aid}", headers=dueno["h"], json={"precio": 350, "negociable": False})
    assert r.status_code == 200 and r.json()["precio"] == 350 and r.json()["negociable"] is False
    assert c.patch(f"/mercado/anuncios/{aid}", headers=admin["h"], json={"precio": 300}).json()["precio"] == 300
    assert c.patch(f"/mercado/anuncios/{aid}", headers=dueno["h"], json={"subcategoria": "lentes"}).status_code == 422


def test_estados_y_pausa(c):
    u = cuenta()
    unico = "Zq" + uuid.uuid4().hex[:8]                             # la base de pruebas acumula anuncios
    aid = crear(c, u, titulo=f"Trident {unico}").json()["id"]
    en_listado = lambda: aid in {x["id"] for x in c.get("/mercado/anuncios", params={"q": unico}).json()["items"]}
    import mercado; mercado._invalidar()
    assert en_listado()
    r = c.post(f"/mercado/anuncios/{aid}/estado", headers=u["h"], json={"estado": "reservado"})
    assert r.json()["estado"] == "reservado"
    r = c.post(f"/mercado/anuncios/{aid}/estado", headers=u["h"], json={"estado": "vendido"})
    assert r.json()["estado"] == "vendido" and r.json()["vendido_at"]
    assert en_listado()                                             # vendido: sigue visible con su marca
    assert c.get("/mercado/anuncios", params={"q": unico, "vendidos": "false"}).json()["total"] == 0
    assert c.post(f"/mercado/anuncios/{aid}/estado", headers=u["h"], json={"estado": "regalado"}).status_code == 422
    c.post(f"/mercado/anuncios/{aid}/estado", headers=u["h"], json={"estado": "disponible"})
    c.post(f"/mercado/anuncios/{aid}/pausa", headers=u["h"], json={"pausado": True})
    assert not en_listado()
    assert c.get(f"/mercado/anuncios/{aid}").status_code == 404          # público: no existe
    assert c.get(f"/mercado/anuncios/{aid}", headers=u["h"]).status_code == 200   # dueño: sí
    c.post(f"/mercado/anuncios/{aid}/pausa", headers=u["h"], json={"pausado": False})
    assert en_listado()


def test_filtros_por_api(c):
    u = cuenta()
    crear(c, u, titulo="Micrófono Shure SM7B usado", categoria="microfonos", subcategoria="microfonos",
          pueblo="ponce", precio=250, entrega="envio")
    j = c.get("/mercado/anuncios", params={"q": "microfono sm7b", "categoria": "microfonos", "pueblo": "ponce",
                                            "precio_max": 300, "entrega": "envio"}).json()
    assert j["total"] >= 1 and all(x["categoria"] == "microfonos" for x in j["items"])
    assert c.get("/mercado/anuncios", params={"orden": "raro"}).status_code == 422
    assert c.get("/mercado/resumen").json()["por_categoria"].get("microfonos", 0) >= 1


def test_limite_de_anuncios_activos(c):
    u = cuenta()
    ids = [crear(c, u).json()["id"] for _ in range(3)]              # MERCADO_MAX_ACTIVOS=3 en pruebas
    assert crear(c, u).status_code == 409
    c.post(f"/mercado/anuncios/{ids[0]}/estado", headers=u["h"], json={"estado": "vendido"})
    assert crear(c, u).status_code == 201                           # los vendidos no cuentan


def test_reordenar_y_borrar(c):
    u = cuenta()
    a = crear(c, u).json()
    nombres = [f.rsplit("/", 1)[1] for f in a["fotos"]]
    r = c.post(f"/mercado/anuncios/{a['id']}/orden-fotos", headers=u["h"], json={"fotos": nombres[::-1]})
    assert [f.rsplit("/", 1)[1] for f in r.json()["fotos"]] == nombres[::-1]
    assert c.post(f"/mercado/anuncios/{a['id']}/orden-fotos", headers=u["h"], json={"fotos": ["otra.webp"]}).status_code == 422
    assert c.delete(f"/mercado/anuncios/{a['id']}", headers=u["h"]).status_code == 204
    assert c.get(f"/mercado/anuncios/{a['id']}", headers=u["h"]).status_code == 404


def test_pocketbase_directo_esta_cerrado():
    """Un navegador sin privilegios no puede leer ni escribir las colecciones del Mercado."""
    u = cuenta()
    for col in ("mercado_anuncios", "mercado_mensajes", "mercado_reportes", "mercado_bloqueos"):
        for h in ({}, u["h"]):
            r = httpx.get(f"{PB}/api/collections/{col}/records", headers=h)
            assert r.status_code in (403, 404) or r.json().get("items") == [], (col, r.status_code)
            r = httpx.post(f"{PB}/api/collections/{col}/records", headers=h, json={"titulo": "x"})
            assert r.status_code in (400, 403, 404), (col, r.status_code)


def test_canal_oculto_hasta_el_primer_directo(c):
    import server
    vendedor, streamer = cuenta(), cuenta(streamer=True)
    server._streamers_cache["data"] = None
    keys = {s["key"] for s in c.get("/streamers").json()}
    assert streamer["key"] in keys and vendedor["key"] not in keys
    assert c.get(f"/profile/{vendedor['key']}").status_code == 404
    # _marcar_primer_directo usa el cliente HTTP del app, que vive en el loop del TestClient
    c.portal.call(server._marcar_primer_directo, vendedor["key"])
    assert vendedor["key"] in {s["key"] for s in c.get("/streamers").json()}
    assert c.get(f"/profile/{vendedor['key']}").status_code == 200
    # y en el Mercado ahora lleva la insignia de streamer
    a = crear(c, vendedor).json()
    assert a["vendedor"]["streamer"] is True and a["vendedor"]["canal"] == f"/{vendedor['key']}/"


def test_notify_sigue_protegido_para_llamadas_externas(c):
    assert c.post("/internal/notify", json={"path": "live/x"}).status_code == 403


def test_reemplazar_fotos_sustituye_las_anteriores(c):
    u = cuenta()
    a = crear(c, u).json()                                          # 2 fotos
    r = c.put(f"/mercado/anuncios/{a['id']}/fotos", headers=u["h"],
              files=[("fotos", ("n.jpg", foto(), "image/jpeg"))] * 3)
    assert r.status_code == 200, r.text
    nuevas = r.json()["fotos"]
    assert len(nuevas) == 3 and not set(nuevas) & set(a["fotos"])
    assert httpx.get(a["fotos"][0]).status_code == 404             # el archivo viejo se borró de verdad
    assert httpx.get(nuevas[0]).status_code == 200
    muchas = [("fotos", ("n.jpg", foto(), "image/jpeg"))] * 11
    assert c.put(f"/mercado/anuncios/{a['id']}/fotos", headers=u["h"], files=muchas).status_code == 422


# ── Contacto, WhatsApp y reportes ──
@pytest.fixture
def turnstile_falso(monkeypatch):
    """Simula Cloudflare: 'ok-<acción>-<n>' vale una sola vez para esa acción (como el real)."""
    import mercado
    usados = set()

    async def verificar(http, token, accion, ip=""):
        if not isinstance(token, str) or not token.startswith(f"ok-{accion}-") or token in usados:
            return False
        usados.add(token)
        return True
    monkeypatch.setattr(mercado.turnstile, "verificar", verificar)
    monkeypatch.setattr(mercado, "ip_cliente", lambda req: req.headers.get("x-ip-prueba", "9.9.9.9"))
    n = iter(range(10**6))
    return lambda accion: f"ok-{accion}-{next(n)}"


def _msg(tok, **kw):
    return {"nombre": "Comprador", "email": "Comprador@Ejemplo.com", "mensaje": "¿Todavía lo tienes? Me interesa.", "token": tok} | kw


def test_contacto_exige_turnstile_y_guarda_registro(c, turnstile_falso):
    import mercado
    u = cuenta()
    aid = crear(c, u).json()["id"]
    assert c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg("")).status_code == 403
    assert c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg(turnstile_falso("reporte"))).status_code == 403
    tok = turnstile_falso("contacto")
    ip = {"x-ip-prueba": "10.0.0." + uuid.uuid4().hex[:2]}
    r = c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg(tok), headers=ip)
    assert r.status_code == 200, r.text
    assert "@" not in json.dumps(r.json())                       # la respuesta no revela correos
    assert c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg(tok), headers=ip).status_code == 403   # reutilizado
    su = {"Authorization": _su()}
    reg = httpx.get(f"{PB}/api/collections/mercado_mensajes/records", headers=su,
                    params={"filter": f'anuncio="{aid}"'}).json()["items"]
    assert len(reg) == 1 and reg[0]["email"] == "comprador@ejemplo.com" and reg[0]["ip"] == ip["x-ip-prueba"]
    assert reg[0]["vendedor"] == u["id"] and reg[0]["anuncio_titulo"]


def test_contacto_honeypot_y_limites(c, turnstile_falso):
    u = cuenta()
    aid = crear(c, u).json()["id"]
    ip = {"x-ip-prueba": "10.1." + uuid.uuid4().hex[:4]}
    r = c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg("", website="http://spam"), headers=ip)
    assert r.status_code == 200                                   # el bot cree que funcionó...
    su = {"Authorization": _su()}
    cuenta_msgs = lambda: httpx.get(f"{PB}/api/collections/mercado_mensajes/records", headers=su,
                                    params={"filter": f'anuncio="{aid}"'}).json()["totalItems"]
    assert cuenta_msgs() == 0                                     # ...pero no se guardó nada
    for _ in range(2):
        assert c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg(turnstile_falso("contacto")), headers=ip).status_code == 200
    assert c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg(turnstile_falso("contacto")), headers=ip).status_code == 429
    assert c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg(turnstile_falso("contacto")),
                  headers={"x-ip-prueba": "10.2." + uuid.uuid4().hex[:4]}).status_code == 200   # otra persona sí puede
    assert c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg(turnstile_falso("contacto"), email="no-es-correo")).status_code == 422


def test_contacto_bloqueado_y_vendido(c, turnstile_falso):
    u = cuenta()
    aid = crear(c, u).json()["id"]
    httpx.post(f"{PB}/api/collections/mercado_bloqueos/records", headers={"Authorization": _su()},
               json={"tipo": "email", "valor": "malo@ejemplo.com"})
    r = c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg(turnstile_falso("contacto"), email="MALO@Ejemplo.com"),
               headers={"x-ip-prueba": "10.3." + uuid.uuid4().hex[:4]})
    assert r.status_code == 403
    c.post(f"/mercado/anuncios/{aid}/estado", headers=u["h"], json={"estado": "vendido"})
    assert c.post(f"/mercado/anuncios/{aid}/contacto", json=_msg(turnstile_falso("contacto"))).status_code == 409


def test_whatsapp_solo_tras_turnstile(c, turnstile_falso):
    u = cuenta()
    aid = crear(c, u).json()["id"]
    assert c.post(f"/mercado/anuncios/{aid}/whatsapp", json={"token": ""}).status_code == 403
    r = c.post(f"/mercado/anuncios/{aid}/whatsapp", json={"token": turnstile_falso("whatsapp")})
    assert r.status_code == 200 and r.json()["whatsapp"] == "7875551234"
    sin = crear(c, u, whatsapp="").json()["id"]
    assert c.post(f"/mercado/anuncios/{sin}/whatsapp", json={"token": turnstile_falso("whatsapp")}).status_code == 404


def test_tres_reportes_ocultan_el_anuncio(c, turnstile_falso):
    import mercado
    u = cuenta()
    unico = "Rp" + uuid.uuid4().hex[:8]
    aid = crear(c, u, titulo=f"Anuncio {unico}").json()["id"]
    rep = lambda ip: c.post(f"/mercado/anuncios/{aid}/reporte", json={"motivo": "estafa", "token": turnstile_falso("reporte")},
                            headers={"x-ip-prueba": ip})
    assert c.post(f"/mercado/anuncios/{aid}/reporte", json={"motivo": "estafa", "token": ""}).status_code == 403
    assert rep("1.1.1.1").status_code == 200
    assert rep("1.1.1.1").status_code == 409                     # uno por persona
    assert rep("2.2.2.2").status_code == 200
    mercado._invalidar()
    assert c.get("/mercado/anuncios", params={"q": unico}).json()["total"] == 1
    assert rep("3.3.3.3").status_code == 200
    assert c.get("/mercado/anuncios", params={"q": unico}).json()["total"] == 0   # oculto
    priv = c.get(f"/mercado/anuncios/{aid}", headers=u["h"]).json()
    assert priv["moderacion"] == "oculto" and priv["reportes"] == 3 and "3 reportes" in priv["motivo_oculto"]
