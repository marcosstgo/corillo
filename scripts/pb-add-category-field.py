"""
Agrega el campo category (text) a la colección streamers y asigna categorías iniciales.
Ejecutar una sola vez:
  python scripts/pb-add-category-field.py
"""
import os, httpx
from dotenv import load_dotenv

load_dotenv("/home/corillo-adm/corillo-bot/.env")

PB_URL         = os.environ.get("PB_URL", "https://pb.corillo.live")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL")
PB_ADMIN_PASS  = os.environ.get("PB_ADMIN_PASS")

INITIAL_CATEGORIES = {
    "katatonia":      "Tecnología",
    "tea":            "Gaming",
    "mira_sanganooo": "Gaming",
    "404":            "Gaming",
    "marcos":         "Tecnología",
    "pataecabra":     "Gaming",
    "streamerpro":    "Tecnología",
    "elhermanoquiles":"Gaming",
    "xxdur3xx":       "Gaming",
    "kamikazepr":     "Gaming",
    "bambua":         "Just Chatting",
    "stinkyfeets":    "Gaming",
    "adrian":         "Gaming",
}

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

        if any(f["name"] == "category" for f in fields):
            print("Campo category ya existe — saltando schema.")
        else:
            fields.append({
                "name":     "category",
                "type":     "text",
                "required": False,
                "options":  {"max": 40},
            })
            r = http.patch(
                f"{PB_URL}/api/collections/streamers",
                headers=headers,
                json={"fields": fields},
            )
            r.raise_for_status()
            print("Campo category agregado.")

        r = http.get(
            f"{PB_URL}/api/collections/streamers/records",
            headers=headers,
            params={"perPage": "200", "fields": "id,key"},
        )
        r.raise_for_status()
        records = r.json().get("items", [])

        updated = 0
        for rec in records:
            cat = INITIAL_CATEGORIES.get(rec["key"])
            if not cat:
                continue
            r = http.patch(
                f"{PB_URL}/api/collections/streamers/records/{rec['id']}",
                headers=headers,
                json={"category": cat},
            )
            r.raise_for_status()
            print(f"  {rec['key']:20} → {cat}")
            updated += 1

        print(f"\n{updated} streamers actualizados.")

if __name__ == "__main__":
    main()
