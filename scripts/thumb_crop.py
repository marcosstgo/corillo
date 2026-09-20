"""
thumb_crop.py — miniaturas nítidas y uniformes (16:9), sin barras negras.

  detect_crop(src, seek)  -> (w, h, x, y) o None   detecta barras negras (letterbox/pillarbox)
  make_jpeg(src, out, ...)                          extrae UN frame, recorta las barras y lo deja
                                                    en WxH (por defecto 1280x720) con calidad alta
  crop_vf(crop)                                     fragmento de filtro ffmpeg reutilizable (previews)

Reglas de seguridad para no recortar de más (una escena oscura no es una barra):
  - se usa la UNIÓN de varios frames (cropdetect reset=0), no uno solo;
  - solo se recorta si las barras suman >= 3% del alto, y nunca se deja menos del 55% del alto;
  - solo se recortan barras de arriba/abajo (las laterales se confunden con interfaz oscura).
NOTA: scripts/vod-process.py lleva una copia de estas funciones (se despliega como archivo suelto).
"""
import re, subprocess

_CROP = re.compile(r"crop=(\d+):(\d+):(\d+):(\d+)")


def _probe(src: str, seek: float = 0):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0:s=x", src], capture_output=True, text=True, timeout=20)
    try:
        w, h = r.stdout.strip().splitlines()[0].split("x")[:2]   # en HLS ffprobe repite la línea por segmento
        return int(w), int(h)
    except Exception:
        return None


def detect_crop(src: str, seek: float = 0, frames: int = 5, timeout: int = 45):
    """Devuelve (w, h, x, y) si hay barras negras que valga la pena recortar; si no, None."""
    dims = _probe(src)
    if not dims:
        return None
    W, H = dims
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if seek:
        cmd += ["-ss", str(seek)]
    cmd += ["-i", src, "-vf", "fps=1,cropdetect=limit=24:round=2:reset=0", "-frames:v", str(frames), "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    found = _CROP.findall(r.stderr)
    if not found:
        return None
    w, h, x, y = (int(v) for v in found[-1])          # con reset=0 el último valor es la unión de todos los frames
    # Solo se recortan barras de ARRIBA y ABAJO (letterbox). Las laterales se ignoran a propósito: en streams son
    # raras y se confunden con paneles oscuros de la interfaz del juego (se cortaría contenido real).
    if H - h < 0.03 * H:
        return None                                    # sin barras apreciables
    if h < 0.55 * H:
        return None                                    # demasiado agresivo: probablemente escena oscura
    return W, h, 0, y


def crop_vf(crop) -> str:
    return f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]}," if crop else ""


def make_jpeg(src: str, out: str, seek: float = 0, crop=None, width: int = 1280, height: int = 720, q: int = 2, timeout: int = 40) -> bool:
    """Un frame de `src` -> JPEG width x height (cover): recorta barras y rellena 16:9 sin deformar."""
    vf = f"{crop_vf(crop)}scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height}"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if seek:
        cmd += ["-ss", str(seek)]
    cmd += ["-i", src, "-vframes", "1", "-vf", vf, "-q:v", str(q), out]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False
