import os, sys
sys.dont_write_bytecode = True
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

# Las pruebas nunca deben hablar con la PocketBase de producción: siempre la desechable
# de scripts/pb-test-server.sh (PB_TEST_URL). setdefault NO basta: el .env no se carga aquí,
# pero forzamos igual por si alguien exportó PB_URL en su shell.
os.environ["PB_URL"] = os.environ.get("PB_TEST_URL", "http://127.0.0.1:8099")
os.environ["PB_ADMIN_EMAIL"] = "test@corillo.test"
os.environ["PB_ADMIN_PASS"] = "testpass123456"
os.environ["CORILLO_REPO"] = str(ROOT)
os.environ["MERCADO_ADMINS"] = "admin_test"
os.environ["MERCADO_MAX_ACTIVOS"] = "3"
os.environ["MERCADO_MAX_CREA_HORA"] = "50"
os.environ["MERCADO_REBUILD"] = ""          # las pruebas nunca recompilan el sitio
