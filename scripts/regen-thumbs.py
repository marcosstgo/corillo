#!/usr/bin/env python3
"""
regen-thumbs.py — vuelve a generar las miniaturas de los VODs existentes: 1280x720 (16:9), sin barras negras.

Las miniaturas viejas eran de 640 px (algunas ni 16:9). Este script:
  1) respalda las miniaturas actuales en un .tgz,
  2) las reemplaza usando scripts/thumb_crop.py (mismo punto de captura que vod-process: 5% de la duración).
Es idempotente y seguro de repetir. Corre con nice/ionice al mínimo. Uso: python3 regen-thumbs.py
"""
import json, os, subprocess, sys, tarfile, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_crop as tc

PB = os.environ.get("PB_URL", "https://pb.corillo.live")
ROOT = os.environ.get("VODS_DIR", "/var/vods/live")
BACKUP = os.environ.get("THUMBS_BACKUP", os.path.expanduser("~/backups-corillo-2026-09-20/thumbs-vods-ANTES.tgz"))


def seek_point(duration: int) -> int:
    return max(60, min(300, int(duration * 0.05))) if duration > 120 else max(1, int(duration * 0.3))


def main():
    items, page = [], 1
    while True:
        d = json.load(urllib.request.urlopen(f"{PB}/api/collections/vods/records?perPage=100&page={page}&fields=id,channel,filename,duration,thumb", timeout=20))
        items += d["items"]
        if page >= d["totalPages"]:
            break
        page += 1
    jobs = []
    for v in items:
        src = os.path.join(ROOT, v["channel"], v["filename"])
        out = os.path.splitext(src)[0] + ".jpg"
        if os.path.exists(src):
            jobs.append((v, src, out))
    if not os.path.exists(BACKUP):
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        with tarfile.open(BACKUP, "w:gz") as t:
            for _, _, out in jobs:
                if os.path.exists(out):
                    t.add(out, arcname=os.path.relpath(out, ROOT))
        print(f"respaldo de miniaturas viejas: {BACKUP}")
    ok = cropped = 0
    for v, src, out in jobs:
        sk = seek_point(v.get("duration") or 0)
        crop = tc.detect_crop(src, seek=sk)
        tmp = out + ".tmp.jpg"
        if tc.make_jpeg(src, tmp, seek=sk, crop=crop):
            os.replace(tmp, out); ok += 1; cropped += bool(crop)
            print(f"ok {v['channel']}/{os.path.basename(out)} {'recortado' if crop else 'sin barras'}")
        else:
            if os.path.exists(tmp): os.remove(tmp)
            print(f"ERROR {src}", file=sys.stderr)
    print(f"listo: {ok}/{len(jobs)} miniaturas regeneradas ({cropped} con barras recortadas)")
    if "--previews" in sys.argv:
        regen_previews(jobs)


def regen_previews(jobs):
    """Clip de 4 s para el hover: 960x540 (16:9), sin barras, ligero (~0.5 MB) y con faststart."""
    ok = 0
    for v, src, _ in jobs:
        out = os.path.splitext(src)[0] + "-preview.mp4"
        if not os.path.exists(out):
            continue
        sk = seek_point(v.get("duration") or 0)
        crop = tc.detect_crop(src, seek=sk)
        vf = f"{tc.crop_vf(crop)}scale=960:540:force_original_aspect_ratio=increase:flags=lanczos,crop=960:540"
        tmp = out + ".tmp.mp4"
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(sk), "-i", src, "-t", "4", "-c:v", "libx264", "-profile:v", "main",
                            "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p", "-vf", vf, "-an", "-movflags", "+faststart", tmp],
                           capture_output=True, timeout=120)
        if r.returncode == 0 and os.path.exists(tmp):
            os.replace(tmp, out); ok += 1
            print(f"ok preview {v['channel']}/{os.path.basename(out)} {os.path.getsize(out)//1024} KB")
        elif os.path.exists(tmp):
            os.remove(tmp)
    print(f"listo: {ok} previews regeneradas")


if __name__ == "__main__":
    main()
