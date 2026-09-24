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
