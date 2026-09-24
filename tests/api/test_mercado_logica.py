"""Lógica pura del Mercado: filtros, orden, estados, validación y fotos (sin red)."""
import io, json
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

import mercado as m

AHORA = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def anuncio(**kw):
    base = {"id": "x", "titulo": "Algo", "categoria": "pc", "subcategoria": "", "marca": "", "modelo": "",
            "descripcion": "", "condicion": "buen-estado", "precio": 100, "pueblo": "aibonito",
            "entrega": "persona", "estado": "disponible", "created": "2026-09-20 10:00:00.000Z",
            "moderacion": "visible", "pausado": False, "vendido_at": ""}
    return base | kw


def test_municipios_son_78_y_categorias_cargan():
    assert len(m.MUNICIPIOS) == 78
    assert {"pc", "microfonos", "webcams", "monitores", "camaras"} <= set(m.CATEGORIAS)


def test_busqueda_ignora_acentos_y_mayusculas():
    a = [anuncio(id="1", titulo="Micrófono Shure SM7B"), anuncio(id="2", titulo="Monitor LG")]
    assert [x["id"] for x in m.filtrar(a, m.Filtros(q="MICROFONO shure"))] == ["1"]
    assert m.filtrar(a, m.Filtros(q="microfono lg")) == []


def test_filtros_categoria_pueblo_precio_condicion_entrega():
    a = [anuncio(id="1", categoria="pc", pueblo="aibonito", precio=400, condicion="buen-estado", entrega="persona"),
         anuncio(id="2", categoria="pc", pueblo="ponce", precio=50, condicion="nuevo", entrega="ambos"),
         anuncio(id="3", categoria="microfonos", pueblo="aibonito", precio=120, condicion="para-piezas", entrega="envio")]
    ids = lambda **kw: [x["id"] for x in m.filtrar(a, m.Filtros(**kw))]
    assert set(ids(categoria="pc")) == {"1", "2"}
    assert set(ids(pueblo="aibonito")) == {"1", "3"}
    assert set(ids(precio_min=100, precio_max=400)) == {"1", "3"}
    assert set(ids(condicion="nuevo,para-piezas")) == {"2", "3"}
    assert set(ids(entrega="envio")) == {"2", "3"}      # "ambos" casa con envío
    assert set(ids(entrega="persona")) == {"1", "2"}


def test_orden_precio_y_recientes_y_vendidos_al_final():
    a = [anuncio(id="caro", precio=900, created="2026-09-01 00:00:00.000Z"),
         anuncio(id="vendido", precio=1, estado="vendido", created="2026-09-23 00:00:00.000Z"),
         anuncio(id="barato", precio=10, created="2026-09-10 00:00:00.000Z")]
    ids = lambda **kw: [x["id"] for x in m.filtrar(a, m.Filtros(**kw))]
    assert ids(orden="precio_asc") == ["barato", "caro", "vendido"]
    assert ids(orden="precio_desc") == ["caro", "barato", "vendido"]
    assert ids() == ["barato", "caro", "vendido"]
    assert ids(vendidos=False) == ["barato", "caro"]


def test_orden_por_cercania():
    a = [anuncio(id="mayaguez", pueblo="mayaguez"), anuncio(id="cayey", pueblo="cayey"),
         anuncio(id="aibonito", pueblo="aibonito")]
    assert [x["id"] for x in m.filtrar(a, m.Filtros(orden="cercania", cerca="aibonito"))] == ["aibonito", "cayey", "mayaguez"]
    assert 5 < m.distancia_km("aibonito", "cayey") < 20


def test_vendido_visible_solo_14_dias_y_pausado_u_oculto_nunca():
    fecha = lambda d: (AHORA - timedelta(days=d)).strftime("%Y-%m-%d %H:%M:%S.000Z")
    assert m.es_publico(anuncio(estado="vendido", vendido_at=fecha(3)), AHORA)
    assert not m.es_publico(anuncio(estado="vendido", vendido_at=fecha(15)), AHORA)
    assert not m.es_publico(anuncio(pausado=True), AHORA)
    assert not m.es_publico(anuncio(moderacion="oculto"), AHORA)
    assert m.es_publico(anuncio(estado="reservado"), AHORA)


def test_transiciones_de_estado():
    assert m.transicion_estado("disponible", "vendido", AHORA)["vendido_at"].startswith("2026-09-24")
    assert m.transicion_estado("vendido", "disponible", AHORA) == {"estado": "disponible", "vendido_at": ""}
    assert "vendido_at" not in m.transicion_estado("vendido", "vendido", AHORA)   # no reinicia el reloj
    assert m.transicion_estado("disponible", "reservado", AHORA)["estado"] == "reservado"
    with pytest.raises(ValueError):
        m.transicion_estado("disponible", "regalado", AHORA)


VALIDO = dict(titulo="MSI MEG Trident X2", categoria="pc", subcategoria="pc-completas", condicion="buen-estado",
              precio=400, negociable=True, pueblo="aibonito", entrega="persona",
              incluye=["i9-13900KF", "  ", "Placa Z790"], falta=["GPU"])


def test_validacion_acepta_lo_correcto_y_limpia():
    a = m.AnuncioIn(**VALIDO, whatsapp="(787) 555-1234")
    assert a.incluye == ["i9-13900KF", "Placa Z790"] and a.whatsapp == "7875551234"
    assert m.AnuncioIn(**VALIDO, whatsapp="+1 939 555 1234").whatsapp == "9395551234"


@pytest.mark.parametrize("cambio", [
    {"categoria": "armas"}, {"pueblo": "nueva-york"}, {"subcategoria": "lentes"},  # sub de otra categoría
    {"precio": -1}, {"precio": 100001}, {"titulo": "abc"}, {"condicion": "usado"},
    {"entrega": "drone"}, {"whatsapp": "555-12"}, {"incluye": "no es lista"}, {"incluye": ["x"] * 26},
])
def test_validacion_rechaza(cambio):
    with pytest.raises(Exception):
        m.AnuncioIn(**(VALIDO | cambio))


def test_campos_del_servidor_no_se_aceptan_del_navegador():
    a = m.AnuncioIn(**VALIDO, estado="vendido", moderacion="visible", reportes=0, vendedor="otro")
    d = a.model_dump()
    assert not {"estado", "moderacion", "reportes", "vendedor"} & set(d)


def _jpeg_con_gps(orientacion=6) -> bytes:
    im = Image.new("RGB", (400, 200), (200, 30, 30))
    exif = Image.Exif()
    exif[0x0112] = orientacion                       # Orientation: rotada 90°
    exif[0x010F] = "Canon"                           # Make
    exif[0x8825] = {1: "N", 2: (18.0, 8.0, 0.0), 3: "W", 4: (66.0, 16.0, 0.0)}  # GPS (Aibonito)
    out = io.BytesIO()
    im.save(out, "JPEG", exif=exif)
    assert Image.open(io.BytesIO(out.getvalue())).getexif().get_ifd(0x8825)   # la prueba tiene GPS de verdad
    return out.getvalue()


def test_foto_sale_webp_sin_exif_ni_gps_y_derecha():
    webp = m.procesar_foto(_jpeg_con_gps())
    im = Image.open(io.BytesIO(webp))
    assert im.format == "WEBP"
    assert im.size == (200, 400)                     # se aplicó la rotación antes de botar el EXIF
    assert not im.getexif() and "exif" not in im.info and "xmp" not in im.info
    assert b"Exif" not in webp and b"Canon" not in webp


def test_foto_grande_se_reduce_y_basura_se_rechaza():
    out = io.BytesIO(); Image.new("RGB", (4000, 3000)).save(out, "PNG")
    assert max(Image.open(io.BytesIO(m.procesar_foto(out.getvalue()))).size) == 1600
    with pytest.raises(ValueError):
        m.procesar_foto(b"<?php echo 1; ?>")


def test_og_es_jpeg_1200x630():
    og = m.imagen_og(m.procesar_foto(_jpeg_con_gps()))
    im = Image.open(io.BytesIO(og))
    assert im.format == "JPEG" and im.size == (1200, 630)
