from datetime import date, timedelta

def test_flow(client):
    meta = client.get("/api/meta").json()
    assert meta["settings"]["my_user_code"] == "MC"
    tpl = {t["name"]: t for t in meta["templates"]}
    assert "WEA-Vermessung" in tpl
    users = {u["code"]: u for u in meta["users"]}

    # Projekt mit Vorlage
    r = client.post("/api/projects", json={"project_number": "26-301", "name": "WP Testfeld", "category": "wea", "client": "Enercon",
                                           "status": "in_bearbeitung", "order_date": "2026-09-14", "offered_weeks": 8,
                                           "template_id": tpl["WEA-Vermessung"]["id"]})
    assert r.status_code == 201, r.text
    pr = r.json()
    assert pr["deadline"] == "2026-11-09" and len(pr["tasks"]) == 11 and pr["progress"] == 0
    assert pr["tasks"][0]["assignee_code"] == "MC" and pr["tasks"][-1]["assignee_code"] == "VERW"
    dues = [t["due_date"] for t in pr["tasks"]]
    assert dues[-2] == "2026-11-09" and dues[-1] > dues[-2]
    assert pr["tasks"][3]["predecessor_id"] == pr["tasks"][2]["id"]

    # doppelte Nummer
    r = client.post("/api/projects", json={"project_number": "26-301", "name": "x"})
    assert r.status_code == 409

    # Aufgabe erledigen -> Fortschritt
    t0 = pr["tasks"][0]
    r = client.post(f"/api/tasks/{t0['id']}/complete")
    assert r.status_code == 200 and r.json()["status"] == "erledigt" and r.json()["progress"] == 100
    pr2 = client.get(f"/api/projects/{pr['id']}").json()
    assert pr2["progress"] > 0 and pr2["open_count"] == 10

    # Frist ändern, ungültig
    r = client.put(f"/api/tasks/{t0['id']}", json={"start_date": "2026-12-01", "due_date": "2026-11-01"})
    assert r.status_code == 422
    r = client.post(f"/api/tasks/{t0['id']}/shift?workdays=2")
    assert r.status_code == 200

    # Aufgabe neu mit Notiz
    r = client.post("/api/tasks", json={"project_id": pr["id"], "title": "Zusatzmessung", "due_date": date.today().isoformat(), "note": "Kunde bestätigt"})
    assert r.status_code == 201 and r.json()["due_state"] == "heute"
    notes = client.get(f"/api/projects/{pr['id']}/notes").json()
    assert notes[0]["content"] == "Kunde bestätigt" and notes[0]["author_code"] == "MC"

    # Überfällig
    r = client.post("/api/tasks", json={"project_id": pr["id"], "title": "Alt", "due_date": (date.today() - timedelta(days=4)).isoformat()})
    tid = r.json()["id"]
    dash = client.get("/api/dashboard").json()
    assert dash["counts"]["overdue"] >= 1 and dash["counts"]["today"] >= 1
    assert any(a["task_id"] == tid and "überfällig" in a["reason"] for a in dash["attention"])
    assert dash["projects_attention"][0]["signal"] == "rot"
    notif = client.get("/api/notifications").json()
    assert any(n["task_id"] == tid for n in notif)

    # Wartet auf Rückmeldung
    r = client.put(f"/api/tasks/{tid}", json={"status": "wartet", "waiting_for": "Betriebsdaten", "waiting_on": "Enercon"})
    assert r.json()["waiting_since"] == date.today().isoformat()
    assert client.get("/api/dashboard").json()["counts"]["waiting_tasks"] == 1

    # Suche, Kalender, Zeitplan
    s = client.get("/api/search?q=26-301").json()
    assert s["projects"][0]["project_number"] == "26-301" and len(s["tasks"]) > 0
    cal = client.get(f"/api/calendar?start={date.today()}&end={date.today()}").json()
    assert cal[0]["tasks"][0]["title"] == "Zusatzmessung"
    sch = client.get("/api/schedule").json()
    assert sch["projects"][0]["project_number"] == "26-301" and len(sch["projects"][0]["tasks"]) > 5

    # Projekte-Liste, Filter Kategorie
    assert len(client.get("/api/projects?category=wea").json()) == 1
    assert len(client.get("/api/projects?category=messung").json()) == 0

    # Export, Backup
    r = client.get("/api/export/excel")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    r = client.get("/api/export/csv?what=projects")
    assert "26-301" in r.text
    r = client.post("/api/backups")
    assert r.status_code == 201 and r.json()["size_bytes"] > 0

    # Protokoll
    act = client.get(f"/api/projects/{pr['id']}/activity").json()
    actions = {a["action"] for a in act}
    assert {"Projekt angelegt", "Vorlage angewendet", "Aufgabe erledigt", "Notiz hinzugefügt", "Aufgabe geändert"} <= actions

    # Projekt abschließen
    r = client.post(f"/api/projects/{pr['id']}/complete", json={"open_tasks": "entfaellt"})
    assert r.json()["status"] == "abgeschlossen" and r.json()["signal"] == "fertig" and r.json()["open_count"] == 0

    # Vorlage anlegen und Vorschau
    r = client.post("/api/templates", json={"name": "Kurz", "category": "messung", "tasks": [{"title": "A", "offset_workdays": 5}, {"title": "B", "offset_workdays": 0}]})
    assert r.status_code == 201
    prev = client.get(f"/api/templates/{r.json()['id']}/preview?deadline=2026-10-30").json()
    assert prev[1]["due_date"] == "2026-10-30" and prev[0]["due_date"] == "2026-10-23"

    # Bearbeiter
    r = client.post("/api/users", json={"code": "xy", "name": "Neu"})
    assert r.status_code == 201 and r.json()["code"] == "XY"
    r = client.delete(f"/api/users/{users['MC']['id']}")
    assert r.status_code == 409

    # Löschen
    assert client.delete(f"/api/projects/{pr['id']}").status_code == 204
    assert client.get(f"/api/projects/{pr['id']}").status_code == 404


def test_folders(client, tmp_path):
    """Die App liest nur: vorhandenen Ordner finden, nie anlegen, nie umbenennen."""
    base = tmp_path / "nas"
    (base / "2026").mkdir(parents=True)
    (base / "2026" / "26-400 Anfrage Alt vorhandener Ordner").mkdir()
    r = client.put("/api/settings", json={"base_path": str(base)})
    assert r.status_code == 200 and "auto_create_folder" not in r.json()

    # vorhandener Ordner wird gefunden und übernommen
    r = client.post("/api/projects", json={"project_number": "26-400", "name": "Neu", "status": "anfrage"})
    assert r.json()["folder_path"].endswith("26-400 Anfrage Alt vorhandener Ordner")
    assert "übernommen" in r.json()["folder_note"]

    # Phasenwechsel: Ordner bleibt, Pfad bleibt, kein Hinweis
    r = client.put(f"/api/projects/{r.json()['id']}", json={"status": "in_bearbeitung"})
    assert r.json()["folder_path"].endswith("26-400 Anfrage Alt vorhandener Ordner")
    assert (base / "2026" / "26-400 Anfrage Alt vorhandener Ordner").is_dir()
    assert r.json()["folder_note"] is None

    # neues Projekt ohne vorhandenen Ordner: nichts wird angelegt
    r = client.post("/api/projects", json={"project_number": "26-401", "name": "WP Test: Nord/Süd?", "status": "anfrage"})
    p = r.json()
    assert p["folder_path"] == "" and p["folder_note"] is None
    assert sorted(e.name for e in (base / "2026").iterdir()) == ["26-400 Anfrage Alt vorhandener Ordner"]
    r = client.put(f"/api/projects/{p['id']}", json={"order_date": "2026-10-05", "offered_weeks": 4})
    assert r.json()["status"] == "beauftragt"
    assert sorted(e.name for e in (base / "2026").iterdir()) == ["26-400 Anfrage Alt vorhandener Ordner"]
    assert client.post(f"/api/projects/{p['id']}/sync-folder").status_code in (404, 405)

    # eigener Pfad bleibt unverändert, Basispfad nicht erreichbar ist kein Fehler
    client.put("/api/settings", json={"base_path": str(tmp_path / "gibtsnicht")})
    r = client.post("/api/projects", json={"project_number": "26-403", "name": "X", "folder_path": "Z:\\irgendwo\\26-403 Auftrag X"})
    assert r.status_code == 201 and r.json()["folder_path"] == "Z:\\irgendwo\\26-403 Auftrag X" and r.json()["folder_note"] is None
    assert not any("Projektordner" in e["action"] for e in client.get("/api/activity").json())


def test_migration(tmp_path):
    import sqlite3
    from sqlalchemy import create_engine
    from app.migrate import migrate
    db = tmp_path / "alt.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, project_number TEXT, name TEXT)")
    con.execute("INSERT INTO projects (project_number, name) VALUES ('25-001', 'Altprojekt')")
    con.commit(); con.close()
    added = migrate(create_engine(f"sqlite:///{db}"))
    assert "projects.category" in added and "projects.status" in added
    con = sqlite3.connect(db)
    row = con.execute("SELECT project_number, name, status, category FROM projects").fetchone()
    assert row == ("25-001", "Altprojekt", "anfrage", "gutachten")
