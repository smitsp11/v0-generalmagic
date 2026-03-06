from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/chase.db")

DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
REMINDER_INTERVAL_SECONDS: int = int(os.getenv("REMINDER_INTERVAL_SECONDS", "30" if DEMO_MODE else "3600"))
BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")

ALLOWED_MEDIA_TYPES: set[str] = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

DATA_DIR: Path = Path(DATABASE_PATH).parent
DATA_DIR.mkdir(parents=True, exist_ok=True)
