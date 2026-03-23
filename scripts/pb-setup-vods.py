#!/usr/bin/env python3
"""
pb-setup-vods.py — Configura PocketBase para el sistema VOD de CORILLO.

Ejecutar una sola vez en el servidor:
  /home/corillo-adm/corillo-vod/venv/bin/python /var/www/stream/scripts/pb-setup-vods.py

Qué hace:
  1. Agrega vod_enabled (bool) y vod_plan (select) a la colección streamers
  2. Crea la colección vods si no existe, o agrega campos faltantes si ya existe
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

    # PocketBase v0.23+ usa "fields", versiones anteriores usan "schema"
    fields = col.get("fields", col.get("schema", []))
    existing = {f["name"] for f in fields}

    added = []
    if "vod_enabled" not in existing:
        fields.append({
            "name": "vod_enabled",
            "type": "bool",
            "required": False,
        })
        added.append("vod_enabled")

    if "vod_plan" not in existing:
        fields.append({
            "name": "vod_plan",
            "type": "select",
            "required": False,
            "maxSelect": 1,
            "values": ["free", "pro"],
        })
        added.append("vod_plan")

    if not added:
        ok("Campos ya existen — sin cambios")
        return

    r = client.patch(
        f"{PB_URL}/api/collections/{col['id']}",
        headers={"Authorization": token},
        json={"fields": fields},
    )
    if r.status_code not in (200, 204):
        err(f"Error actualizando streamers ({r.status_code}): {r.text}")

    for field in added:
        ok(f"Campo '{field}' agregado")


VOD_FIELDS = [
    {"name": "channel",  "type": "text",   "required": True},
    {"name": "filename", "type": "text",   "required": True},
    {"name": "filepath", "type": "text",   "required": True},
    {"name": "duration", "type": "number", "required": False},
    {"name": "size",     "type": "number", "required": False},
    {"name": "date",     "type": "date",   "required": False},
]


def setup_vods(client: httpx.Client, token: str):
    print("\n[2/2] Colección vods")
    existing = get_collection(client, token, "vods")

    if not existing:
        # Crear colección nueva
        r = client.post(
            f"{PB_URL}/api/collections",
            headers={"Authorization": token},
            json={
                "name": "vods",
                "type": "base",
                "listRule":   "",    # público — sin auth
                "viewRule":   "",
                "createRule": None,  # solo admin
                "updateRule": None,
                "deleteRule": None,
                "fields": VOD_FIELDS,
            },
        )
        if r.status_code not in (200, 201):
            err(f"Error creando colección vods ({r.status_code}): {r.text}")
        ok("Colección 'vods' creada con 6 campos")
        return

    # Colección existe — verificar campos faltantes
    current_fields = existing.get("fields", existing.get("schema", []))
    existing_names = {f["name"] for f in current_fields}
    missing = [f for f in VOD_FIELDS if f["name"] not in existing_names]

    if not missing:
        ok("Colección 'vods' ya existe con todos los campos")
        return

    # Agregar campos faltantes
    updated_fields = current_fields + missing
    r = client.patch(
        f"{PB_URL}/api/collections/{existing['id']}",
        headers={"Authorization": token},
        json={
            "fields":     updated_fields,
            "listRule":   "",
            "viewRule":   "",
            "createRule": None,
            "updateRule": None,
            "deleteRule": None,
        },
    )
    if r.status_code not in (200, 204):
        err(f"Error actualizando vods ({r.status_code}): {r.text}")

    for f in missing:
        ok(f"Campo '{f['name']}' agregado a vods")


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
