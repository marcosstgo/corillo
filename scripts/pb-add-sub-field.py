#!/usr/bin/env python3
"""
pb-add-sub-field.py — Agrega el campo 'sub' (status/categoría) a la colección streamers.

Ejecutar una sola vez en el servidor:
  /home/corillo-adm/corillo-vod/venv/bin/python /var/www/stream/scripts/pb-add-sub-field.py
"""
import os, sys
import httpx
from dotenv import load_dotenv

load_dotenv("/home/corillo-adm/corillo-bot/.env")

PB_URL         = os.environ.get("PB_URL",         "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS",  "")


def log(msg): print(f"  {msg}")
def ok(msg):  print(f"  ✓ {msg}")
def err(msg): print(f"  ✗ {msg}"); sys.exit(1)


def main():
    print("CORILLO — Agregar campo 'sub' a streamers")
    print("=" * 40)

    with httpx.Client(timeout=15) as client:
        log("Autenticando con PocketBase...")
        r = client.post(
            f"{PB_URL}/api/collections/_superusers/auth-with-password",
            json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
        )
        if r.status_code != 200:
            err(f"Auth failed ({r.status_code}): {r.text}")
        token = r.json()["token"]
        ok("Autenticado")

        log("Leyendo colección streamers...")
        r = client.get(f"{PB_URL}/api/collections/streamers", headers={"Authorization": token})
        if r.status_code == 404:
            err("Colección 'streamers' no encontrada")
        r.raise_for_status()
        col = r.json()

        fields = col.get("fields", col.get("schema", []))
        existing = {f["name"] for f in fields}

        if "sub" in existing:
            ok("Campo 'sub' ya existe — sin cambios")
            return

        fields.append({
            "name":     "sub",
            "type":     "text",
            "required": False,
        })

        r = client.patch(
            f"{PB_URL}/api/collections/{col['id']}",
            headers={"Authorization": token},
            json={"fields": fields},
        )
        if r.status_code not in (200, 204):
            err(f"Error actualizando streamers ({r.status_code}): {r.text}")

        ok("Campo 'sub' agregado a la colección streamers")

    print("\n" + "=" * 40)
    print("Listo.")


if __name__ == "__main__":
    main()
