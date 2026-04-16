"""
pb-setup-vod-upload.py
Agrega el campo upload_enabled (bool) a la colección streamers
y lo activa para marcos y streamerpro.

Ejecutar una sola vez:
    python scripts/pb-setup-vod-upload.py
"""
import os, sys, httpx
from dotenv import load_dotenv

load_dotenv()

PB_URL   = os.environ.get("PB_URL", "https://pb.corillo.live")
EMAIL    = os.environ.get("PB_ADMIN_EMAIL", "")
PASSWORD = os.environ.get("PB_ADMIN_PASS", "")

ENABLE_FOR = {"marcos", "streamerpro"}

def main():
    with httpx.Client(timeout=15) as c:
        # Auth
        r = c.post(f"{PB_URL}/api/collections/_superusers/auth-with-password",
                   json={"identity": EMAIL, "password": PASSWORD})
        r.raise_for_status()
        token = r.json()["token"]
        headers = {"Authorization": token}

        # Obtener ID de la colección streamers
        r = c.get(f"{PB_URL}/api/collections/streamers", headers=headers)
        r.raise_for_status()
        col = r.json()
        col_id = col["id"]
        fields = col.get("fields", [])

        # Verificar si ya existe
        if any(f["name"] == "upload_enabled" for f in fields):
            print("Campo upload_enabled ya existe — saltando creación.")
        else:
            fields.append({
                "name":     "upload_enabled",
                "type":     "bool",
                "required": False,
                "system":   False,
                "presentable": False,
                "options":  {},
            })
            r2 = c.patch(f"{PB_URL}/api/collections/{col_id}",
                         headers=headers, json={"fields": fields})
            r2.raise_for_status()
            print("Campo upload_enabled agregado.")

        # Activar para los streamers indicados
        for key in ENABLE_FOR:
            r3 = c.get(f"{PB_URL}/api/collections/streamers/records",
                       headers=headers,
                       params={"filter": f'key="{key}"', "perPage": 1})
            items = r3.json().get("items", [])
            if not items:
                print(f"  {key}: no encontrado.")
                continue
            rec_id = items[0]["id"]
            already = items[0].get("upload_enabled", False)
            if already:
                print(f"  {key}: ya tiene upload_enabled=true.")
                continue
            r4 = c.patch(f"{PB_URL}/api/collections/streamers/records/{rec_id}",
                         headers=headers, json={"upload_enabled": True})
            r4.raise_for_status()
            print(f"  {key}: upload_enabled activado.")

    print("Listo.")

if __name__ == "__main__":
    if not EMAIL or not PASSWORD:
        sys.exit("Faltan PB_ADMIN_EMAIL / PB_ADMIN_PASS en el entorno.")
    main()
