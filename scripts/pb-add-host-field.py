"""
Agrega el campo host (boolean) a la colección streamers y marca katatonia=true.
Ejecutar una sola vez:
  python scripts/pb-add-host-field.py
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

        r = http.get(f"{PB_URL}/api/collections/streamers", headers=headers)
        r.raise_for_status()
        col = r.json()

        fields = col.get("fields", [])
        if any(f["name"] == "host" for f in fields):
            print("Campo host ya existe — saltando schema.")
        else:
            fields.append({
                "name":     "host",
                "type":     "bool",
                "required": False,
            })
            r = http.patch(
                f"{PB_URL}/api/collections/streamers",
                headers=headers,
                json={"fields": fields},
            )
            r.raise_for_status()
            print("Campo host agregado.")

        # Buscar katatonia y marcarlo como host
        r = http.get(
            f"{PB_URL}/api/collections/streamers/records",
            headers=headers,
            params={"filter": 'key="katatonia"', "perPage": 1},
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            print("WARN: katatonia no encontrado en PocketBase.")
            return
        kata_id = items[0]["id"]
        r = http.patch(
            f"{PB_URL}/api/collections/streamers/records/{kata_id}",
            headers=headers,
            json={"host": True},
        )
        r.raise_for_status()
        print(f"katatonia ({kata_id}) marcado como host=true.")

if __name__ == "__main__":
    main()
