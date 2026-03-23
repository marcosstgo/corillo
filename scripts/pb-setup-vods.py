#!/usr/bin/env python3
"""
pb-setup-vods.py — Configura PocketBase para el sistema VOD de CORILLO.

Ejecutar una sola vez en el servidor:
  /home/corillo-adm/corillo-vod/venv/bin/python /var/www/stream/scripts/pb-setup-vods.py

Qué hace:
  1. Agrega vod_enabled (bool) y vod_plan (select) a la colección streamers
  2. Crea la colección vods si no existe
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


def admin_token(client: httpx.Client) -> str:
    r = client.post(
        f"{PB_URL}/api/collections/_superusers/auth-with-password",
        json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
    )
    if r.status_code != 200:
        err(f"Auth failed ({r.status_code}): {r.text}")
    return r.json()["token"]


def get_collection(client: httpx.Client, token: str, name: str) -> dict | None:
    r = client.get(f"{PB_URL}/api/collections/{name}", headers={"Authorization": token})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def setup_streamers(client: httpx.Client, token: str):
    print("\n[1/2] Colección streamers — agregando campos VOD")
    col = get_collection(client, token, "streamers")
    if not col:
        err("Colección 'streamers' no encontrada")

    schema = col.get("schema", [])
    existing = {f["name"] for f in schema}

    added = []
    if "vod_enabled" not in existing:
        schema.append({
            "name": "vod_enabled",
            "type": "bool",
            "required": False,
            "options": {},
        })
        added.append("vod_enabled")

    if "vod_plan" not in existing:
        schema.append({
            "name": "vod_plan",
            "type": "select",
            "required": False,
            "options": {"maxSelect": 1, "values": ["free", "pro"]},
        })
        added.append("vod_plan")

    if not added:
        ok("Campos ya existen — sin cambios")
        return

    r = client.patch(
        f"{PB_URL}/api/collections/{col['id']}",
        headers={"Authorization": token},
        json={"schema": schema},
    )
    if r.status_code not in (200, 204):
        err(f"Error actualizando streamers ({r.status_code}): {r.text}")

    for field in added:
        ok(f"Campo '{field}' agregado")


def setup_vods(client: httpx.Client, token: str):
    print("\n[2/2] Colección vods")
    existing = get_collection(client, token, "vods")
    if existing:
        ok("Colección 'vods' ya existe — sin cambios")
        return

    r = client.post(
        f"{PB_URL}/api/collections",
        headers={"Authorization": token},
        json={
            "name": "vods",
            "type": "base",
            "listRule":   "",   # público — sin auth
            "viewRule":   "",
            "createRule": None, # solo admin
            "updateRule": None,
            "deleteRule": None,
            "schema": [
                {"name": "channel",  "type": "text",   "required": True,  "options": {}},
                {"name": "filename", "type": "text",   "required": True,  "options": {}},
                {"name": "filepath", "type": "text",   "required": True,  "options": {}},
                {"name": "duration", "type": "number", "required": False, "options": {}},
                {"name": "size",     "type": "number", "required": False, "options": {}},
                {"name": "date",     "type": "date",   "required": False, "options": {}},
            ],
        },
    )
    if r.status_code not in (200, 201):
        err(f"Error creando colección vods ({r.status_code}): {r.text}")
    ok("Colección 'vods' creada con 6 campos")


def main():
    print("CORILLO — PocketBase VOD setup")
    print("=" * 40)

    with httpx.Client(timeout=15) as client:
        log("Autenticando con PocketBase...")
        token = admin_token(client)
        ok("Autenticado")

        setup_streamers(client, token)
        setup_vods(client, token)

    print("\n" + "=" * 40)
    print("Setup completado.")


if __name__ == "__main__":
    main()
