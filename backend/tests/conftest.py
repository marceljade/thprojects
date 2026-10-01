import os, tempfile, pathlib
import pytest
from fastapi.testclient import TestClient

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PMTH_DATA", str(tmp_path / "data"))
    from app import config
    config.DATA_DIR = tmp_path / "data"
    config.BACKUP_DIR = config.DATA_DIR / "backups"
    config.DB_PATH = config.DATA_DIR / "projekte.db"
    from app.main import create_app
    app = create_app(f"sqlite:///{config.DB_PATH}", serve_static=False)
    with TestClient(app) as c:
        yield c
