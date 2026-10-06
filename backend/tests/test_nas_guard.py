"""Der Schreibschutz blockt jeden schreibenden Dateizugriff unterhalb des Basispfads, lässt Lesen und alles andere zu."""
import os
import shutil
from pathlib import Path

import pytest

from app.services import nas_guard
from app.services.nas_guard import NasWriteBlocked


def test_guard_blocks_writes_under_base(client, tmp_path):
    base = tmp_path / "nas"
    (base / "2026" / "26-900 Auftrag Alt").mkdir(parents=True)
    (base / "2026" / "26-900 Auftrag Alt" / "bericht.txt").write_text("alt", encoding="utf-8")
    other = tmp_path / "woanders"
    other.mkdir()

    r = client.put("/api/settings", json={"base_path": str(base)}).json()
    assert r["nas_write_guard"] is True and nas_guard.active()

    # Lesen geht
    assert [p.name for p in (base / "2026").iterdir()] == ["26-900 Auftrag Alt"]
    assert (base / "2026" / "26-900 Auftrag Alt" / "bericht.txt").read_text(encoding="utf-8") == "alt"
    with open(base / "2026" / "26-900 Auftrag Alt" / "bericht.txt", encoding="utf-8") as f:
        assert f.read() == "alt"

    # Schreiben unterhalb des Basispfads wird geblockt, über jede Schnittstelle
    with pytest.raises(NasWriteBlocked):
        (base / "2026" / "26-901 Auftrag Neu").mkdir()
    with pytest.raises(NasWriteBlocked):
        os.makedirs(base / "2026" / "26-902", exist_ok=True)
    with pytest.raises(NasWriteBlocked):
        os.rename(base / "2026" / "26-900 Auftrag Alt", base / "2026" / "26-900 Anfrage Alt")
    with pytest.raises(NasWriteBlocked):
        (base / "2026" / "26-900 Auftrag Alt").rename(base / "2026" / "26-900 Anfrage Alt")
    with pytest.raises(NasWriteBlocked):
        shutil.move(str(other), str(base / "2026" / "verschoben"))
    with pytest.raises(NasWriteBlocked):
        shutil.rmtree(base / "2026")
    with pytest.raises(NasWriteBlocked):
        (base / "2026" / "26-900 Auftrag Alt" / "bericht.txt").unlink()
    with pytest.raises(NasWriteBlocked):
        open(base / "2026" / "neu.txt", "w")
    with pytest.raises(NasWriteBlocked):
        (base / "2026" / "neu.txt").write_text("x")
    with pytest.raises(NasWriteBlocked):
        (base / "2026" / "neu.txt").touch()
    with pytest.raises(NasWriteBlocked):
        shutil.copy(str(base / "2026" / "26-900 Auftrag Alt" / "bericht.txt"), str(base / "kopie.txt"))
    # andere Schreibweise desselben Pfads (Groß/Klein, Slash) wird genauso erkannt
    with pytest.raises(NasWriteBlocked):
        Path(str(base).upper().replace("\\", "/") + "/2026/x").mkdir()
    # nichts hat sich geändert
    assert sorted(p.name for p in base.rglob("*")) == ["2026", "26-900 Auftrag Alt", "bericht.txt"]

    # außerhalb des Basispfads bleibt alles erlaubt (Datenbank, Sicherungen, Exporte)
    (other / "sub").mkdir()
    (other / "sub" / "f.txt").write_text("ok")
    shutil.rmtree(other / "sub")
    assert client.post("/api/backups").status_code == 201

    # die Meldung ist in der Stimme der App
    with pytest.raises(NasWriteBlocked, match="Die App schreibt nicht auf dem NAS"):
        (base / "x").mkdir()

    # Basispfad leeren -> keine Sperre mehr nötig
    r = client.put("/api/settings", json={"base_path": ""}).json()
    assert r["nas_write_guard"] is False
    (base / "2026" / "jetzt erlaubt").mkdir()


def test_guard_in_api_response(client, tmp_path, monkeypatch):
    """Sollte je ein Service doch schreiben wollen, kommt eine klare Fehlermeldung statt eines Absturzes."""
    base = tmp_path / "nas"
    base.mkdir()
    client.put("/api/settings", json={"base_path": str(base)})
    from app.services import projects

    def boese(db, project_id):
        (base / "2026").mkdir()
        return {}
    monkeypatch.setattr(projects, "open_folder", boese)
    p = client.post("/api/projects", json={"project_number": "26-903", "name": "X"}).json()
    r = client.post(f"/api/projects/{p['id']}/open-folder")
    assert r.status_code == 403 and "Die App schreibt nicht auf dem NAS" in r.json()["detail"]
    assert not (base / "2026").exists()
