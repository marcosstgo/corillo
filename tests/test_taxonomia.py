"""La taxonomía es compartida entre /equipo/ y /mercado/: no puede haber huecos."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATS = json.loads((ROOT / "src/data/categorias.json").read_text())
EQUIPO = (ROOT / "src/data/equipo.ts").read_text()


def test_cada_tipo_de_equipo_tiene_categoria_unica():
    kinds = re.findall(r"'([a-z]+)'", re.search(r"export type EquipoKind =([^;]+);", EQUIPO).group(1))
    usados = set(re.findall(r"kind: '([a-z]+)'", EQUIPO))
    assert usados <= set(kinds)
    for k in kinds:
        dueñas = [c["slug"] for c in CATS if k in c["equipoKinds"]]
        assert len(dueñas) == 1, f"'{k}' debe estar en exactamente una categoría (está en {dueñas})"


def test_slugs_validos_y_sin_repetir():
    slugs = [c["slug"] for c in CATS]
    assert len(slugs) == len(set(slugs))
    for c in CATS:
        assert re.fullmatch(r"[a-z0-9-]+", c["slug"]) and c["es"] and c["en"]
        subs = [s["slug"] for s in c["sub"]]
        assert len(subs) == len(set(subs)) and all(s["es"] and s["en"] for s in c["sub"])


def test_diccionarios_es_en_tienen_las_mismas_claves():
    def claves(d, p=""):
        out = set()
        for k, v in d.items():
            out |= claves(v, p + k + ".") if isinstance(v, dict) else {p + k}
        return out
    es = json.loads((ROOT / "src/i18n/es.json").read_text())
    en = json.loads((ROOT / "src/i18n/en.json").read_text())
    assert claves(es) == claves(en), claves(es) ^ claves(en)


def test_ninguna_categoria_choca_con_rutas_del_mercado():
    fijas = set(re.search(r"RUTAS_FIJAS = \[([^\]]+)\]", (ROOT / "src/data/mercado.ts").read_text()).group(1).replace("'", "").replace(" ", "").split(","))
    assert fijas and not fijas & {c["slug"] for c in CATS}
