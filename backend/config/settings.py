import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
LOG_DIR = BACKEND_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'business_data.db'}")
APP_ENV = os.getenv("APP_ENV", "production")
DEFAULT_USER = os.getenv("DEFAULT_USER", "system")
