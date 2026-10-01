"""Pfade und Grundeinstellungen. Alles Lokale liegt neben der Anwendung im Ordner data/."""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Projektmanagement T&H"
VERSION = "1.0.0"

BASE_DIR = Path(os.environ.get("PMTH_HOME", Path(__file__).resolve().parent.parent)).resolve()
DATA_DIR = Path(os.environ.get("PMTH_DATA", BASE_DIR / "data")).resolve()
BACKUP_DIR = DATA_DIR / "backups"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = DATA_DIR / "projekte.db"

HOST = os.environ.get("PMTH_HOST", "127.0.0.1")
PORT = int(os.environ.get("PMTH_PORT", "8765"))

# Später PostgreSQL: PMTH_DATABASE_URL=postgresql+psycopg://user:pw@host/db
DATABASE_URL = os.environ.get("PMTH_DATABASE_URL", f"sqlite:///{DB_PATH}")

BACKUPS_KEEP = 30


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
