"""
Agrega el campo peak_viewers (number) a la colección vods.
Ejecutar una sola vez:
  python scripts/pb-add-peak-viewers-field.py
"""
import os, httpx
from dotenv import load_dotenv

load_dotenv("/home/corillo-adm/corillo-bot/.env")

PB_URL         = os.environ.get("PB_URL", "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS")

def main():
    with httpx.Client(timeout=10) as http:
        r = http.post(
            f"{PB_URL}/api/collections/_superusers/auth-with-password",
            json={"identity": PB_ADMIN_EMAIL, "password": PB_ADMIN_PASS},
        )
        r.raise_for_status()
        token = r.json()["token"]
        headers = {"Authorization": token}

        r = http.get(f"{PB_URL}/api/collections/vods", headers=headers)
        r.raise_for_status()
        col = r.json()
        fields = col.get("fields", [])

        if any(f["name"] == "peak_viewers" for f in fields):
            print("Campo peak_viewers ya existe — nada que hacer.")
            return

        fields.append({
            "name":     "peak_viewers",
            "type":     "number",
            "required": False,
            "options":  {"min": 0},
        })
        r = http.patch(
            f"{PB_URL}/api/collections/vods",
            headers=headers,
            json={"fields": fields},
        )
        r.raise_for_status()
        print("Campo peak_viewers agregado a la colección vods.")

if __name__ == "__main__":
    main()
