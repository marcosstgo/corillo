"""
pb-setup-vod-upload.py
Agrega el campo upload_enabled (bool) a la colección streamers
y lo activa para marcos y streamerpro.

Ejecutar una sola vez:
    python3 scripts/pb-setup-vod-upload.py
"""
import os, sys, json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

PB_URL   = os.environ.get("PB_URL", "https://pb.corillo.live")
EMAIL    = os.environ.get("PB_ADMIN_EMAIL", "")
PASSWORD = os.environ.get("PB_ADMIN_PASS", "")

ENABLE_FOR = {"marcos", "streamerpro"}


def pb_request(method, path, token=None, body=None):
    url = f"{PB_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except HTTPError as e:
        raise RuntimeError(f"{method} {path} → {e.code}: {e.read().decode()}")


def main():
    # Auth
    r = pb_request("POST", "/api/collections/_superusers/auth-with-password",
                   body={"identity": EMAIL, "password": PASSWORD})
    token = r["token"]

    # Obtener colección streamers
    col    = pb_request("GET", "/api/collections/streamers", token=token)
    col_id = col["id"]
    fields = col.get("fields", [])

    if any(f["name"] == "upload_enabled" for f in fields):
        print("Campo upload_enabled ya existe — saltando.")
    else:
        fields.append({
            "name": "upload_enabled", "type": "bool",
            "required": False, "system": False,
            "presentable": False, "options": {},
        })
        pb_request("PATCH", f"/api/collections/{col_id}", token=token, body={"fields": fields})
        print("Campo upload_enabled agregado.")

    # Activar para los streamers indicados
    for key in ENABLE_FOR:
        r2 = pb_request("GET",
            f"/api/collections/streamers/records?filter=key%3D%22{key}%22&perPage=1",
            token=token)
        items = r2.get("items", [])
        if not items:
            print(f"  {key}: no encontrado.")
            continue
        rec = items[0]
        if rec.get("upload_enabled"):
            print(f"  {key}: ya tiene upload_enabled=true.")
            continue
        pb_request("PATCH", f"/api/collections/streamers/records/{rec['id']}",
                   token=token, body={"upload_enabled": True})
        print(f"  {key}: upload_enabled activado.")

    print("Listo.")


if __name__ == "__main__":
    if not EMAIL or not PASSWORD:
        sys.exit("Faltan PB_ADMIN_EMAIL / PB_ADMIN_PASS en el entorno.")
    main()
