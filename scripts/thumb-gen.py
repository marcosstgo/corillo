#!/usr/bin/env python3
"""
thumb-gen.py — miniaturas de los canales en vivo (servicio corillo-thumbs, en corillo-server). Reescrito 31-oct-2026.

Pedido de Marcos: la tarjeta "En vivo ahora" tiene que mostrar una imagen clara del stream, nunca negra.

Por cada canal en vivo, cada INTERVAL segundos:
  1. Graba MUESTRA segundos del RTSP interno de mediamtx y saca un cuadro por segundo (PNG sin pérdida) más una copia
     chiquita en gris (384x216) para medir.
  2. Califica cada cuadro: brillo medio, contraste y nitidez (diferencia entre píxeles vecinos). Se descartan los
     oscuros (menús, pantallas de carga), los planos (fundidos, pantallas de un color) y gana el más nítido.
  3. Barras negras: filas casi negras pegadas arriba/abajo, en TODOS los cuadros buenos a la vez (una escena oscura
     no es una barra). Solo se recortan si suman >= 3 % del alto y queda al menos el 55 % de la imagen.
  4. Recorta, lleva a 1280x720 (cover, lanczos) y guarda <canal>.jpg de forma atómica.
Si ningún cuadro sirve se deja la miniatura anterior. Un canal nuevo tiene miniatura a los ~15 s de salir en vivo.

Sale en https://media.corillo.live/assets/thumbs/<canal>.jpg (portada, /streamers, /reels, og:image del canal).

Variables: MEDIAMTX_API (http://127.0.0.1:9997), SRC_BASE (rtsp://127.0.0.1:8554),
           THUMB_DIR (/var/www/stream/assets/thumbs), THUMB_INTERVAL (60).
"""
import json, logging, os, shutil, subprocess, sys, tempfile, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MEDIAMTX_API = os.environ.get("MEDIAMTX_API", "http://127.0.0.1:9997")
SRC_BASE     = os.environ.get("SRC_BASE", "rtsp://127.0.0.1:8554")   # el HLS de mediamtx 1.21 pide sesión; el RTSP interno no
THUMB_DIR    = Path(os.environ.get("THUMB_DIR", "/var/www/stream/assets/thumbs"))
INTERVAL     = int(os.environ.get("THUMB_INTERVAL", "60"))
REVISAR      = 15          # cada cuánto se mira quién está en vivo (para que un canal nuevo no espere un minuto)
MUESTRA      = 6           # segundos de video que se miran → 6 cuadros candidatos
SALIDA       = (1280, 720)
GW, GH       = 384, 216    # tamaño de la copia en gris para medir
MIN_BRILLO   = 35          # 0-255: menos que esto es una escena oscura
MIN_CONTRASTE = 18         # desviación estándar: menos es un fundido o una pantalla de un solo color
NEGRO        = 16          # una fila con brillo medio menor es "barra"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [thumbs] %(levelname)s %(message)s", stream=sys.stdout)
log = logging.getLogger("thumbs")


def en_vivo() -> list[str]:
    try:
        with urllib.request.urlopen(f"{MEDIAMTX_API}/v3/paths/list", timeout=5) as r:
            items = json.load(r).get("items", [])
    except Exception as e:
        log.warning(f"API de mediamtx: {e}")
        return []
    return [i["name"].removeprefix("live/") for i in items
            if i.get("ready") and i["name"].startswith("live/")
            and not i["name"].endswith(("_rtc", "_low"))]   # _rtc es solo audio; _low es la copia 720p del mismo canal


def medir(gris: bytes) -> dict:
    """Brillo, contraste, nitidez y barras de un cuadro en gris GWxGH."""
    filas = [gris[y * GW:(y + 1) * GW] for y in range(GH)]
    medias = [sum(f) / GW for f in filas]
    arriba = 0
    while arriba < GH // 2 and medias[arriba] < NEGRO:
        arriba += 1
    abajo = 0
    while abajo < GH // 2 and medias[GH - 1 - abajo] < NEGRO:
        abajo += 1
    # Lo demás se mide solo en el contenido (sin las barras), saltando de 2 en 2 píxeles: sobra para comparar.
    zona = range(arriba, GH - abajo)
    vals, nitidez = [], 0
    for y in zona:
        f = filas[y]
        vals.extend(f[::2])
        nitidez += sum(abs(f[x] - f[x + 2]) for x in range(0, GW - 2, 2))
        if y + 2 < GH - abajo:
            g = filas[y + 2]
            nitidez += sum(abs(f[x] - g[x]) for x in range(0, GW, 2))
    n = max(1, len(vals))
    brillo = sum(vals) / n
    contraste = (sum((v - brillo) ** 2 for v in vals) / n) ** 0.5
    return {"brillo": brillo, "contraste": contraste, "nitidez": nitidez / n, "arriba": arriba, "abajo": abajo}


def capturar(key: str) -> bool:
    tmp = Path(tempfile.mkdtemp(prefix=f"thumb-{key}-"))
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-rtsp_transport", "tcp", "-i", f"{SRC_BASE}/live/{key}",
             "-t", str(MUESTRA), "-an",
             "-filter_complex", f"fps=1,split=2[a][b];[b]scale={GW}:{GH}:flags=area,format=gray[g]",
             "-map", "[a]", "-frames:v", str(MUESTRA), str(tmp / "c%02d.png"),
             "-map", "[g]", "-frames:v", str(MUESTRA), "-f", "rawvideo", str(tmp / "gris.raw")],
            capture_output=True, timeout=MUESTRA + 30)
        cuadros = sorted(tmp.glob("c*.png"))
        crudo = (tmp / "gris.raw").read_bytes() if (tmp / "gris.raw").exists() else b""
        if r.returncode != 0 or not cuadros:
            log.warning(f"{key}: ffmpeg no sacó cuadros ({r.stderr.decode(errors='replace').strip()[-200:]})")
            return False
        medidas = [medir(crudo[i * GW * GH:(i + 1) * GW * GH]) for i in range(min(len(cuadros), len(crudo) // (GW * GH)))]
        buenos = [(m, cuadros[i]) for i, m in enumerate(medidas)
                  if m["brillo"] >= MIN_BRILLO and m["contraste"] >= MIN_CONTRASTE]
        if not buenos:
            resumen = ", ".join(f"{m['brillo']:.0f}/{m['contraste']:.0f}" for m in medidas)
            log.info(f"{key}: ningún cuadro claro (brillo/contraste: {resumen}); se deja la miniatura anterior")
            return False
        m, mejor = max(buenos, key=lambda b: b[0]["nitidez"])

        # Barras: las que están en TODOS los cuadros buenos.
        arriba = min(b[0]["arriba"] for b in buenos)
        abajo = min(b[0]["abajo"] for b in buenos)
        recorte = ""
        if arriba + abajo >= 0.03 * GH and GH - arriba - abajo >= 0.55 * GH:
            # +1 fila de margen para no dejar el borde gris de la barra
            recorte = (f"crop=iw:ih*{(GH - arriba - abajo - 2) / GH:.5f}:0:ih*{(arriba + 1) / GH:.5f},")
        W, H = SALIDA
        tmp_jpg = THUMB_DIR / f".{key}.tmp.jpg"
        r = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(mejor), "-vf",
             f"{recorte}scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}",
             "-q:v", "2", "-map_metadata", "-1", str(tmp_jpg)],
            capture_output=True, timeout=30)
        if r.returncode != 0 or not tmp_jpg.exists():
            log.warning(f"{key}: no se pudo guardar el JPEG ({r.stderr.decode(errors='replace').strip()[-200:]})")
            return False
        tmp_jpg.replace(THUMB_DIR / f"{key}.jpg")
        barras = f", barras {arriba * 100 // GH}%+{abajo * 100 // GH}% recortadas" if recorte else ""
        log.info(f"{key}: miniatura lista (cuadro {mejor.stem[1:]} de {len(medidas)}, {len(buenos)} claros, "
                 f"brillo {m['brillo']:.0f}, contraste {m['contraste']:.0f}, nitidez {m['nitidez']:.1f}{barras})")
        return True
    except Exception as e:
        log.warning(f"{key}: {e}")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run():
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    for viejo in THUMB_DIR.glob("*-preview*.mp4"):   # el generador anterior hacía videos de muestra que nadie usa
        viejo.unlink(missing_ok=True)
    log.info(f"corillo-thumbs: cada {INTERVAL}s, {MUESTRA} cuadros por canal → {THUMB_DIR}")
    ultima: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        while True:
            ahora = time.time()
            vivos = en_vivo()
            toca = [k for k in vivos if ahora - ultima.get(k, 0) >= INTERVAL]
            for k in toca:
                ultima[k] = ahora
            list(pool.map(capturar, toca))
            for k in list(ultima):
                if k not in vivos:
                    del ultima[k]          # si vuelve a salir en vivo, miniatura nueva enseguida
            time.sleep(REVISAR)


if __name__ == "__main__":
    run()
