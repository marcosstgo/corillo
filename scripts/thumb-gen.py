#!/usr/bin/env python3
"""
thumb-gen.py — Genera thumbnails y previews en tiempo real de streams en vivo.

Corre como daemon, revisa la API de MediaMTX cada INTERVAL segundos,
captura un JPEG y un clip MP4 de 4s de cada stream activo con ffmpeg.

Archivos generados:
  {THUMB_DIR}/{key}.jpg          — thumbnail estático (actualizado cada ciclo)
  {THUMB_DIR}/{key}-preview.mp4  — preview de hover (4s, muted, faststart)

Variables de entorno:
  MEDIAMTX_API    — URL base de la API de MediaMTX  (default: http://127.0.0.1:9997)
  HLS_BASE        — URL base del servidor HLS        (default: http://127.0.0.1:8888)
  THUMB_DIR       — Directorio de salida             (default: /var/www/stream/assets/thumbs)
  THUMB_INTERVAL  — Segundos entre capturas          (default: 60)
"""
import os, subprocess, time, logging, sys
from pathlib import Path

import httpx

MEDIAMTX_API = os.environ.get("MEDIAMTX_API", "http://127.0.0.1:9997")
HLS_BASE     = os.environ.get("HLS_BASE",     "http://127.0.0.1:8888")
THUMB_DIR    = Path(os.environ.get("THUMB_DIR", "/var/www/stream/assets/thumbs"))
INTERVAL     = int(os.environ.get("THUMB_INTERVAL", "60"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [thumbs] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/corillo-thumbs.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def get_live_keys() -> list[str]:
    try:
        r = httpx.get(f"{MEDIAMTX_API}/v3/paths/list", timeout=5)
        items = r.json().get("items", [])
        return [
            item["name"].removeprefix("live/")
            for item in items
            if item.get("ready") and item["name"].startswith("live/")
        ]
    except Exception as e:
        log.warning(f"API error: {e}")
        return []


BLACK_THRESHOLD = 18   # 0-255; frames con brillo medio < umbral se descartan
MAX_RETRIES     = 3
RETRY_DELAY     = 6    # segundos entre reintentos cuando el frame es negro


def mean_brightness(path: Path) -> int:
    """Retorna el brillo medio (0-255) de una imagen usando ffmpeg scale=1x1."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-i", str(path),
             "-vf", "scale=1:1,format=gray",
             "-frames:v", "1", "-f", "rawvideo", "pipe:1"],
            capture_output=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout[0]
    except Exception:
        pass
    return 128  # asumir OK si no se puede medir


def capture_thumb(key: str) -> bool:
    url = f"{HLS_BASE}/live/{key}/index.m3u8"
    out = THUMB_DIR / f"{key}.jpg"
    tmp = THUMB_DIR / f"{key}.tmp.jpg"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", url,
                 "-vframes", "1", "-q:v", "3", "-vf", "scale=640:-1",
                 str(tmp)],
                capture_output=True, timeout=20,
            )
            if r.returncode != 0 or not tmp.exists():
                tmp.unlink(missing_ok=True)
                log.warning(f"thumb failed for {key} attempt {attempt} (rc={r.returncode})")
                break

            brightness = mean_brightness(tmp)
            if brightness >= BLACK_THRESHOLD:
                tmp.replace(out)
                if attempt > 1:
                    log.info(f"Thumb OK (brightness={brightness}) for {key} on attempt {attempt}")
                return True

            log.warning(f"Black frame for {key} (brightness={brightness}) attempt {attempt}/{MAX_RETRIES} — retrying in {RETRY_DELAY}s")
            tmp.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        except Exception as e:
            log.warning(f"capture_thumb {key} attempt {attempt}: {e}")
            tmp.unlink(missing_ok=True)
            break

    log.warning(f"Thumb gave up for {key} after {MAX_RETRIES} attempts")
    return False


def capture_preview(key: str) -> bool:
    url = f"{HLS_BASE}/live/{key}/index.m3u8"
    out = THUMB_DIR / f"{key}-preview.mp4"
    tmp = THUMB_DIR / f"{key}-preview.tmp.mp4"
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", url,
             "-t", "4",
             "-c:v", "libx264", "-profile:v", "baseline", "-level:v", "3.1",
             "-preset", "ultrafast", "-crf", "32",
             "-vf", "scale=640:-2",
             "-an",
             "-movflags", "+faststart",
             str(tmp)],
            capture_output=True, timeout=60,
        )
        if r.returncode == 0 and tmp.exists():
            tmp.replace(out)
            return True
        tmp.unlink(missing_ok=True)
        log.warning(f"preview failed for {key} (rc={r.returncode})")
    except Exception as e:
        log.warning(f"capture_preview {key}: {e}")
        tmp.unlink(missing_ok=True)
    return False


def run():
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"Starting thumb-gen — interval={INTERVAL}s dir={THUMB_DIR}")
    while True:
        keys = get_live_keys()
        if keys:
            log.info(f"Live: {keys}")
        for key in keys:
            if capture_thumb(key):
                log.info(f"Thumb OK: {key}")
            if capture_preview(key):
                log.info(f"Preview OK: {key}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    run()
