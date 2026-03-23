#!/usr/bin/env python3
"""
vod-process.py — Post-procesamiento de grabaciones MediaMTX para CORILLO VOD.

Llamado por MediaMTX via runOnRecordSegmentComplete.
Variables de entorno provistas por MediaMTX:
  MTX_PATH        — path del stream (ej: live/katatonia)
  MTX_RECORD_PATH — ruta del archivo grabado
"""
import os, sys, subprocess, logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv("/home/corillo-adm/corillo-bot/.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [vod] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/corillo-vod.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

PB_URL         = os.environ.get("PB_URL",         "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS",  "")

PLANS = {
    "free": {"keep": 5},
    "pro":  {"keep": None},   # sin límite
}

# ── PocketBase helpers ────────────────────────────────────────────

def pb_token() -> str:
    r = httpx.post(
        f"{PB_URL}/api/collections/_superusers/auth-with-password",
        json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def get_streamer(channel: str, token: str) -> dict | None:
    r = httpx.get(
        f"{PB_URL}/api/collections/streamers/records",
        headers={"Authorization": token},
        params={
            "filter": f'key="{channel}" && active=true',
            "fields": "id,key,vod_enabled,vod_plan",
        },
        timeout=10,
    )
    items = r.json().get("items", [])
    return items[0] if items else None


def save_vod(channel: str, filepath: str, duration: int, size: int, thumb: str, token: str) -> str:
    p = Path(filepath)
    r = httpx.post(
        f"{PB_URL}/api/collections/vods/records",
        headers={"Authorization": token},
        json={
            "channel":  channel,
            "filename": p.name,
            "filepath": filepath,
            "duration": duration,
            "size":     size,
            "thumb":    thumb,
            "date":     datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.000Z'),
        },
        timeout=10,
    )
    return r.json().get("id", "")


def apply_retention(channel: str, keep: int, token: str):
    if keep is None:
        return
    r = httpx.get(
        f"{PB_URL}/api/collections/vods/records",
        headers={"Authorization": token},
        params={
            "filter":  f'channel="{channel}"',
            "sort":    "-date",
            "perPage": 500,
            "fields":  "id,filepath",
        },
        timeout=10,
    )
    items = r.json().get("items", [])
    for item in items[keep:]:
        fp = Path(item.get("filepath", ""))
        if fp.exists():
            fp.unlink()
            log.info(f"retention: deleted {fp}")
        httpx.delete(
            f"{PB_URL}/api/collections/vods/records/{item['id']}",
            headers={"Authorization": token},
            timeout=10,
        )

# ── File helpers ──────────────────────────────────────────────────

def get_duration(filepath: str) -> int:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            capture_output=True, text=True, timeout=60,
        )
        return int(float(result.stdout.strip()))
    except Exception:
        return 0


def generate_thumbnail(filepath: Path, duration: int) -> Path | None:
    """Extrae un frame del video como thumbnail JPEG. Retorna el path o None."""
    thumb_path = filepath.with_suffix(".jpg")
    # Capturar frame a los 10s, o al 20% de la duración, lo que sea menor
    seek = min(10, max(1, int(duration * 0.2))) if duration > 0 else 5
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(seek), "-i", str(filepath),
             "-vframes", "1", "-q:v", "3", "-vf", "scale=640:-1",
             str(thumb_path)],
            capture_output=True, timeout=60,
        )
        if thumb_path.exists():
            return thumb_path
    except Exception as e:
        log.warning(f"Thumbnail generation failed: {e}")
    return None

# ── Main ──────────────────────────────────────────────────────────

def main():
    mtx_path    = os.environ.get("MTX_PATH", "")
    record_path = os.environ.get("MTX_RECORD_PATH", "")

    if not mtx_path or not record_path:
        log.error("MTX_PATH or MTX_RECORD_PATH not set — aborting")
        sys.exit(1)

    channel  = mtx_path.removeprefix("live/")
    filepath = Path(record_path)

    if not filepath.exists():
        log.error(f"File not found: {record_path}")
        sys.exit(1)

    log.info(f"Processing VOD: channel={channel} file={filepath.name} size={filepath.stat().st_size}")

    try:
        token    = pb_token()
        streamer = get_streamer(channel, token)
    except Exception as e:
        log.error(f"PocketBase unreachable: {e} — keeping file to avoid data loss")
        sys.exit(0)

    if not streamer:
        log.warning(f"Streamer not found in PocketBase: {channel} — deleting file")
        filepath.unlink(missing_ok=True)
        return

    if not streamer.get("vod_enabled", False):
        log.info(f"VODs disabled for {channel} — deleting file")
        filepath.unlink(missing_ok=True)
        return

    plan_name = streamer.get("vod_plan", "free")
    plan      = PLANS.get(plan_name, PLANS["free"])

    duration = get_duration(str(filepath))
    size     = filepath.stat().st_size

    thumb_path = generate_thumbnail(filepath, duration)
    thumb_url  = f"/vods/{channel}/{thumb_path.name}" if thumb_path else ""
    if thumb_path:
        log.info(f"Thumbnail generated: {thumb_path.name}")
    else:
        log.warning(f"No thumbnail generated for {filepath.name}")

    vod_id = save_vod(channel, str(filepath), duration, size, thumb_url, token)
    log.info(f"VOD saved: {channel} — {filepath.name} ({duration}s, {size//1024//1024}MB) — id={vod_id}")

    apply_retention(channel, plan["keep"], token)
    log.info(f"Retention applied: plan={plan_name} keep={plan['keep']}")


if __name__ == "__main__":
    main()
