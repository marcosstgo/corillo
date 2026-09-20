#!/usr/bin/env python3
"""
Genera versiones livianas de los reels para que carguen rápido en el celular.

  <nombre>.mp4      original (1080x1920, 6-12 Mbps)  -> se conserva; es el que se descarga
  <nombre>_720.mp4  720x1280  ~1.6 Mbps               -> se sirve por defecto
  <nombre>_480.mp4  480x854   ~0.7 Mbps               -> conexiones lentas / ahorro de datos

Es idempotente: solo crea lo que falta. Uso:
  python3 reel-variants.py                 # todos los reels que falten
  python3 reel-variants.py <ruta.mp4> ...  # solo esos archivos
Corre con nice/ionice al mínimo para no afectar el streaming en vivo.
"""
import glob, os, re, subprocess, sys

ROOT = os.environ.get("REELS_DIR", "/var/vods/reels")
TIERS = {
    "720": dict(w=720, crf=27, maxrate="1800k", buf="3600k", abr="96k"),
    "480": dict(w=480, crf=30, maxrate="800k", buf="1600k", abr="64k"),
}
VARIANT_RE = re.compile(r"_(720|480)\.mp4$")


def make(src: str, tier: str) -> bool:
    t = TIERS[tier]
    out = re.sub(r"\.mp4$", f"_{tier}.mp4", src)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return False
    tmp = out + ".tmp.mp4"
    cmd = ["nice", "-n", "19", "ionice", "-c3", "ffmpeg", "-y", "-v", "error", "-i", src,
           "-vf", f"scale=w='min({t['w']},iw)':h=-2:flags=lanczos",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(t["crf"]), "-maxrate", t["maxrate"], "-bufsize", t["buf"],
           "-pix_fmt", "yuv420p", "-threads", "4", "-c:a", "aac", "-b:a", t["abr"], "-movflags", "+faststart", tmp]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(tmp):
        print(f"ERROR {tier} {src}: {r.stderr[-200:]}", file=sys.stderr)
        if os.path.exists(tmp): os.remove(tmp)
        return False
    os.replace(tmp, out)
    print(f"ok {tier} {os.path.basename(out)} {os.path.getsize(src)/1e6:.1f} MB -> {os.path.getsize(out)/1e6:.1f} MB")
    return True


def main():
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "*", "*.mp4")))
    n = 0
    for f in files:
        if VARIANT_RE.search(f) or f.endswith(".tmp.mp4"):
            continue
        for tier in TIERS:
            n += make(f, tier)
    print(f"listo: {n} variantes nuevas")


if __name__ == "__main__":
    main()
