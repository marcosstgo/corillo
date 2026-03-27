"""
One-time script: crea la colección push_subscriptions en PocketBase.
Corre una sola vez en setup inicial.

Uso:
  cd /home/corillo-adm/corillo-bot
  source .env && python /var/www/stream/scripts/pb-setup-push.py

Genera VAPID keys (requiere pywebpush instalado):
  python -c "
from py_vapid import Vapid
v = Vapid()
v.generate_keys()
print('VAPID_PUBLIC_KEY =', v.public_key.decode())
print('VAPID_PRIVATE_KEY=', v.private_key.decode())
"

Agregar al .env:
  VAPID_PUBLIC_KEY=<public key>
  VAPID_PRIVATE_KEY=<private key>
  VAPID_MAILTO=hello@corillo.live
"""
import os, httpx
from dotenv import load_dotenv

load_dotenv()
PB_URL         = os.environ["PB_URL"]
PB_ADMIN_EMAIL = os.environ["PB_ADMIN_EMAIL"]
PB_ADMIN_PASS  = os.environ["PB_ADMIN_PASS"]

with httpx.Client(timeout=10) as http:
    r = http.post(
        f"{PB_URL}/api/collections/_superusers/auth-with-password",
        json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
    )
    token = r.json()["token"]
    headers = {"Authorization": token}

    schema = {
        "name": "push_subscriptions",
        "type": "base",
        "fields": [
            {"name": "channel",      "type": "text",    "required": True},
            {"name": "endpoint",     "type": "text",    "required": True},
            {"name": "subscription", "type": "json",    "required": True},
        ],
        "indexes": ["CREATE INDEX idx_push_channel ON push_subscriptions (channel)"],
        "listRule": None,
        "viewRule": None,
        "createRule": None,
        "updateRule": None,
        "deleteRule": None,
    }

    r = http.post(f"{PB_URL}/api/collections", headers=headers, json=schema)
    if r.status_code in (200, 201):
        print("✓ Colección push_subscriptions creada")
    elif r.status_code == 400 and "already exists" in r.text:
        print("⚠ Colección ya existe — OK")
    else:
        print(f"✗ Error {r.status_code}: {r.text}")
