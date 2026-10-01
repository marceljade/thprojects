from app.services.folders import parse_folder_path as parse


def test_parse_folder_path():
    r = parse(r"P:\Projekte\2026\26-234 Anfrage WP Testfeld, Nachmessung")
    assert r == {"project_number": "26-234", "name": "WP Testfeld, Nachmessung", "status": "anfrage"}
    r = parse(r"P:\Projekte\2026\26-234 Auftrag WP Testfeld\ ")
    assert r == {"project_number": "26-234", "name": "WP Testfeld", "status": "beauftragt"}
    # Forward-Slashes, file:///-Präfix und Anführungszeichen (Kopieren aus dem Explorer)
    assert parse("file:///P:/Projekte/2026/26-001 Anfrage Nord")["name"] == "Nord"
    assert parse(r'"P:\Projekte\2026\26-001 Auftrag Nord"')["status"] == "beauftragt"
    # Nur der Ordnername, ohne Basis
    assert parse("26-002 Anfrage Süd")["project_number"] == "26-002"


def test_parse_folder_path_rejects():
    assert parse("") is None
    assert parse(r"P:\Projekte\2026") is None
    assert parse(r"P:\Projekte\2026\26-234 WP Testfeld") is None          # Phasenwort fehlt
    assert parse(r"P:\Projekte\2026\26-234 Angebot WP Testfeld") is None  # kein gültiges Phasenwort
    assert parse(r"P:\Projekte\2026\2026-234 Anfrage X") is None          # Nummer nicht JJ-NNN
    assert parse(r"P:\Projekte\2026\26-234 Anfrage") is None              # Name fehlt
