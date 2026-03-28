"""
Agrega el campo stream_title a la colección streamers en PocketBase.
Ejecutar una sola vez:
  python scripts/pb-add-stream-title.py
"""
import os, httpx
from dotenv import load_dotenv

load_dotenv("/home/corillo-adm/corillo-bot/.env")

PB_URL         = os.environ.get("PB_URL", "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS")

def main():
    with httpx.Client(timeout=10) as http:
        # Auth
        r = http.post(
            f"{PB_URL}/api/collections/_superusers/auth-with-password",
            json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
        )
        r.raise_for_status()
        token = r.json()["token"]
        headers = {"Authorization": token}

        # Get streamers collection schema
        r = http.get(f"{PB_URL}/api/collections/streamers", headers=headers)
        r.raise_for_status()
        col = r.json()

        # Check field doesn't already exist
        fields = col.get("fields", [])
        if any(f["name"] == "stream_title" for f in fields):
            print("Campo stream_title ya existe — nada que hacer.")
            return

        # Add field
        fields.append({
            "name":     "stream_title",
            "type":     "text",
            "required": False,
            "options":  {"max": 80},
        })

        r = http.patch(
            f"{PB_URL}/api/collections/streamers",
            headers=headers,
            json={"fields": fields},
        )
        r.raise_for_status()
        print("Campo stream_title agregado correctamente.")

if __name__ == "__main__":
    main()
