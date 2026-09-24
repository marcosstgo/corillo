import os, sys
import sys; sys.dont_write_bytecode = True
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

# Las pruebas nunca deben hablar con la PocketBase de producción.
os.environ.setdefault("PB_URL", os.environ.get("PB_TEST_URL", "http://127.0.0.1:8099"))
os.environ.setdefault("PB_ADMIN_EMAIL", "test@corillo.test")
os.environ.setdefault("PB_ADMIN_PASS", "testpass123456")
