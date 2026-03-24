#!/usr/bin/env python3
"""
vod-cleanup-short.py — Limpieza one-time de VODs con duración < MIN_DURATION.

Borra los registros de PocketBase y los archivos MP4/JPG/preview asociados.

Uso:
    python scripts/vod-cleanup-short.py             # dry-run (solo muestra qué borraría)
    python scripts/vod-cleanup-short.py --delete    # borra de verdad

Variables de entorno requeridas (carga desde corillo-bot/.env en el servidor):
    PB_URL, PB_ADMIN_EMAIL, PB_ADMIN_PASS
"""
import os, sys, argparse
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv("/home/corillo-adm/corillo-bot/.env")

PB_URL         = os.environ.get("PB_URL",         "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS",  "")

MIN_DURATION = 600  # segundos — mismo threshold que vod-process.py


def pb_token() -> str:
    r = httpx.post(
        f"{PB_URL}/api/collections/_superusers/auth-with-password",
        json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def fetch_short_vods(token: str) -> list:
    """Retorna todos los VODs con duration < MIN_DURATION."""
    results = []
    page = 1
    while True:
        r = httpx.get(
            f"{PB_URL}/api/collections/vods/records",
            headers={"Authorization": token},
            params={
                "filter":  f"duration < {MIN_DURATION}",
                "sort":    "date",
                "perPage": 200,
                "page":    page,
                "fields":  "id,channel,filename,filepath,duration,size",
            },
            timeout=10,
        )
        data = r.json()
        items = data.get("items", [])
        results.extend(items)
        if page >= data.get("totalPages", 1):
            break
        page += 1
    return results


def delete_vod(vod: dict, token: str, dry_run: bool):
    fp = Path(vod.get("filepath", ""))
    stem = fp.stem  # ej: 2026-03-20_14-30-00

    # Archivos asociados: .mp4, .jpg, -preview.mp4
    associated = [fp, fp.with_suffix(".jpg"), fp.with_name(stem + "-preview.mp4")]

    for f in associated:
        if f.exists():
            if dry_run:
                print(f"  [dry] would delete file: {f}")
            else:
                f.unlink()
                print(f"  deleted file: {f}")
        # Si el archivo ya no existe, no es un error — puede que nunca se haya generado

    if dry_run:
        print(f"  [dry] would delete PB record: {vod['id']}")
    else:
        httpx.delete(
            f"{PB_URL}/api/collections/vods/records/{vod['id']}",
            headers={"Authorization": token},
            timeout=10,
        )
        print(f"  deleted PB record: {vod['id']}")


def main():
    parser = argparse.ArgumentParser(description="Limpia VODs cortos de CORILLO.")
    parser.add_argument("--delete", action="store_true", help="Ejecutar borrado real (sin este flag es dry-run)")
    args = parser.parse_args()

    dry_run = not args.delete

    if dry_run:
        print("=== DRY RUN — no se borra nada. Usa --delete para borrar de verdad. ===\n")
    else:
        print("=== MODO DELETE — borrando archivos y registros ===\n")

    token = pb_token()
    vods  = fetch_short_vods(token)

    if not vods:
        print(f"No hay VODs con duración < {MIN_DURATION}s. Nada que limpiar.")
        return

    total_size = sum(v.get("size", 0) for v in vods)
    print(f"Encontrados {len(vods)} VODs con duración < {MIN_DURATION}s "
          f"({total_size / 1024 / 1024:.1f} MB en total)\n")

    for vod in vods:
        print(f"[{vod['channel']}] {vod['filename']} — {vod['duration']}s, {vod.get('size', 0)//1024}KB")
        delete_vod(vod, token, dry_run)

    print(f"\n{'[dry-run] Listo.' if dry_run else 'Listo. Todos los VODs cortos eliminados.'}")


if __name__ == "__main__":
    main()
