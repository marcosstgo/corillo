#!/usr/bin/env python3
"""
pb-setup-reels.py — Crea la colección 'reels' en PocketBase para CORILLO.

Ejecutar una sola vez:
  /home/corillo-adm/corillo-vod/venv/bin/python /var/www/stream/scripts/pb-setup-reels.py
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


def admin_token(client):
    r = client.post(
        f"{PB_URL}/api/collections/_superusers/auth-with-password",
        json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
    )
    if r.status_code != 200:
        err(f"Auth failed ({r.status_code}): {r.text}")
    return r.json()["token"]


def get_collection(client, token, name):
    r = client.get(f"{PB_URL}/api/collections/{name}", headers={"Authorization": token})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


REELS_FIELDS = [
    {"name": "channel",   "type": "text",   "required": True},
    {"name": "vod_id",    "type": "text",   "required": False},
    {"name": "filename",  "type": "text",   "required": True},
    {"name": "filepath",  "type": "text",   "required": True},
    {"name": "duration",  "type": "number", "required": False},
    {"name": "start_sec", "type": "number", "required": False},
    {"name": "end_sec",   "type": "number", "required": False},
    {"name": "thumb",     "type": "text",   "required": False},
    {"name": "public",    "type": "bool",   "required": False},
    {"name": "date",      "type": "date",   "required": False},
    {"name": "title",     "type": "text",   "required": False},
    {"name": "size",      "type": "number", "required": False},
]

with httpx.Client(timeout=15) as client:
    token = admin_token(client)
    headers = {"Authorization": token}

    print("\n[1/1] Colección reels")
    existing = get_collection(client, token, "reels")

    if existing:
        ok("Colección 'reels' ya existe — verificando campos")
        current_fields = existing.get("fields", existing.get("schema", []))
        existing_names = {f["name"] for f in current_fields}
        added = []
        for f in REELS_FIELDS:
            if f["name"] not in existing_names:
                current_fields.append(f)
                added.append(f["name"])
        if added:
            r = client.patch(
                f"{PB_URL}/api/collections/{existing['id']}",
                headers=headers,
                json={"fields": current_fields},
            )
            if r.status_code not in (200, 204):
                err(f"Error actualizando ({r.status_code}): {r.text}")
            for name in added:
                ok(f"Campo '{name}' agregado")
        else:
            ok("Todos los campos ya existen")
    else:
        r = client.post(
            f"{PB_URL}/api/collections",
            headers=headers,
            json={
                "name":       "reels",
                "type":       "base",
                "listRule":   "public = true || @request.auth.key = channel",
                "viewRule":   "public = true || @request.auth.key = channel",
                "createRule": None,
                "updateRule": None,
                "deleteRule": "@request.auth.key = channel",
                "fields":     REELS_FIELDS,
            },
        )
        if r.status_code not in (200, 201):
            err(f"Error creando colección ({r.status_code}): {r.text}")
        ok("Colección 'reels' creada")

print("\nListo.\n")
