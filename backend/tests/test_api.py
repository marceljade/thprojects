import pytest
from datetime import date, timedelta

from app.services import nas_guard

from app.services import nas_guard

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
    """Die App liest nur: vorhandenen Ordner finden, Abweichung melden, nie anlegen, nie umbenennen."""
    base = tmp_path / "nas"
    (base / "2026").mkdir(parents=True)
    (base / "2026" / "26-400 Anfrage Neu").mkdir()
    r = client.put("/api/settings", json={"base_path": str(base)})
    assert r.status_code == 200 and "auto_create_folder" not in r.json() and "auto_rename_folder" not in r.json()

    # Vorschau fürs Formular
    r = client.get("/api/projects/folder-lookup", params={"project_number": "26-400", "status": "anfrage", "name": "Neu"}).json()
    assert r["found"].endswith("26-400 Anfrage Neu") and r["expected"].endswith("26-400 Anfrage Neu")
    r = client.get("/api/projects/folder-lookup", params={"project_number": "26-401", "status": "anfrage", "name": "X"}).json()
    assert r["found"] is None and r["expected"].endswith("26-401 Anfrage X")

    # vorhandener Ordner wird gefunden und übernommen, Name passt
    r = client.post("/api/projects", json={"project_number": "26-400", "name": "Neu", "status": "anfrage"})
    p = r.json()
    assert p["folder_path"].endswith("26-400 Anfrage Neu") and "übernommen" in p["folder_note"]
    assert p["folder_matches"] is True and p["expected_folder_name"] == "26-400 Anfrage Neu"
    assert client.get(f"/api/projects/{p['id']}").json()["folder_note"] is None

    # Phasenwechsel: Ordner bleibt, Hinweis zum Umbenennen
    r = client.put(f"/api/projects/{p['id']}", json={"status": "in_bearbeitung"}).json()
    assert r["folder_path"].endswith("26-400 Anfrage Neu") and r["folder_matches"] is False
    assert r["expected_folder_name"] == "26-400 Auftrag Neu"
    assert r["folder_note"] == "Ordner heißt noch Anfrage. Benenne ihn auf dem NAS in Auftrag um."
    assert (base / "2026" / "26-400 Anfrage Neu").is_dir()

    # Name geändert: Hinweis mit erwartetem Namen
    r = client.put(f"/api/projects/{p['id']}", json={"name": "Neu 2", "status": "anfrage"}).json()
    assert r["folder_note"] == "Ordnername weicht ab. Erwartet: 26-400 Anfrage Neu 2."

    # kein Ordner vorhanden: Hinweis zum Anlegen, nichts wird angelegt
    r = client.post("/api/projects", json={"project_number": "26-401", "name": "WP Test: Nord/Süd?", "status": "anfrage"}).json()
    assert r["folder_path"] == "" and r["folder_note"].startswith("Kein Ordner mit 26-401 im Jahresordner gefunden.")
    assert client.post(f"/api/projects/{r['id']}/sync-folder").status_code in (404, 405)

    # Nutzer legt den Ordner später selbst an: beim nächsten Öffnen wird er übernommen
    with nas_guard.as_user():
        (base / "2026" / "26-401 Anfrage WP Test Nord Süd").mkdir()
    r = client.get(f"/api/projects/{r['id']}").json()
    assert r["folder_path"].endswith("26-401 Anfrage WP Test Nord Süd") and "übernommen" in r["folder_note"]
    assert any(e["action"] == "Projektordner übernommen" for e in client.get("/api/activity").json())

    # Nutzer benennt auf dem NAS um: beim nächsten Öffnen wird der neue Name gefunden
    with nas_guard.as_user():
        (base / "2026" / "26-401 Anfrage WP Test Nord Süd").rename(base / "2026" / "26-401 Auftrag WP Test Nord Süd")
    r = client.get(f"/api/projects/{r['id']}").json()
    assert r["folder_path"].endswith("26-401 Auftrag WP Test Nord Süd")

    # eigener Pfad bleibt, Basispfad nicht erreichbar ist kein Fehler
    client.put("/api/settings", json={"base_path": str(tmp_path / "gibtsnicht")})
    r = client.post("/api/projects", json={"project_number": "26-403", "name": "X", "folder_path": "Z:\\irgendwo\\26-403 Auftrag X"})
    assert r.status_code == 201 and r.json()["folder_path"] == "Z:\\irgendwo\\26-403 Auftrag X"


def _tree(base):
    return sorted(str(p.relative_to(base)) for p in base.rglob("*"))


@pytest.mark.parametrize("with_folder", [True, False])
def test_nas_bleibt_unveraendert(client, tmp_path, with_folder):
    base = tmp_path / "nas"
    (base / "2026").mkdir(parents=True)
    if with_folder:
        (base / "2026" / "26-500 Anfrage Alt").mkdir()
        (base / "2026" / "26-500 Anfrage Alt" / "angebot.pdf").write_bytes(b"x")
    client.put("/api/settings", json={"base_path": str(base)})
    before = _tree(base)

    p = client.post("/api/projects", json={"project_number": "26-500", "name": "Alt", "status": "anfrage", "template_id": 1}).json()
    assert _tree(base) == before
    client.put(f"/api/projects/{p['id']}", json={"status": "angebot"})
    client.put(f"/api/projects/{p['id']}", json={"order_date": "2026-10-05", "offered_weeks": 4})
    assert client.get(f"/api/projects/{p['id']}").json()["status"] == "beauftragt"
    assert _tree(base) == before
    client.put(f"/api/projects/{p['id']}", json={"name": "Alt umbenannt"})
    client.post(f"/api/projects/{p['id']}/open-folder")
    client.post(f"/api/projects/{p['id']}/complete", params={"open_tasks": "erledigt"})
    client.delete(f"/api/projects/{p['id']}")
    assert _tree(base) == before


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


def test_migration_rounds(tmp_path):
    """Alte Datenbank ohne Runden: jedes Projekt bekommt Runde 1, alle Aufgaben hängen daran."""
    import sqlite3
    from sqlalchemy import create_engine
    from app.migrate import migrate
    db = tmp_path / "alt.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, project_number TEXT, name TEXT, status TEXT, order_date DATE, offered_weeks REAL, completed_at DATE)")
    con.execute("INSERT INTO projects (project_number, name, status, order_date, offered_weeks) VALUES ('25-001', 'Laufend', 'in_bearbeitung', '2026-09-01', 6)")
    con.execute("INSERT INTO projects (project_number, name, status, completed_at) VALUES ('25-002', 'Fertig', 'abgeschlossen', '2026-09-20')")
    con.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, project_id INTEGER, title TEXT)")
    con.execute("INSERT INTO tasks (project_id, title) VALUES (1, 'A'), (1, 'B'), (2, 'C')")
    con.commit(); con.close()
    engine = create_engine(f"sqlite:///{db}")
    added = migrate(engine)
    assert "tasks.round_id" in added and any(a.startswith("project_rounds: Runde 1 für 2") for a in added)
    con = sqlite3.connect(db)
    rounds = con.execute("SELECT project_id, number, title, status, order_date, offered_weeks, closed_at FROM project_rounds ORDER BY project_id").fetchall()
    assert rounds == [(1, 1, "Erstauftrag", "in_bearbeitung", "2026-09-01", 6.0, None), (2, 1, "Erstauftrag", "abgeschlossen", None, None, "2026-09-20")]
    assert con.execute("SELECT COUNT(*) FROM tasks WHERE round_id IS NULL").fetchone()[0] == 0
    assert con.execute("SELECT DISTINCT round_id FROM tasks WHERE project_id = 1").fetchall() == [(1,)]
    # zweiter Lauf ändert nichts mehr
    assert not [a for a in migrate(engine) if "Runde" in a or "round" in a]
    con.close()


def _tree(base):
    return sorted(str(p.relative_to(base)) for p in base.rglob("*"))


def test_follow_up(client, tmp_path):
    base = tmp_path / "nas"
    (base / "2026" / "26-600 Auftrag Erst").mkdir(parents=True)
    client.put("/api/settings", json={"base_path": str(base)})
    before = _tree(base)
    meta = client.get("/api/meta").json()
    tpl = meta["templates"][0]["id"]

    p = client.post("/api/projects", json={"project_number": "26-600", "name": "Erst", "status": "in_bearbeitung",
                                           "order_date": "2026-09-01", "offered_weeks": 4, "template_id": tpl}).json()
    assert p["round_number"] == 1 and p["round_title"] == "Erstauftrag" and len(p["rounds"]) == 1
    assert all(t["round_id"] == p["rounds"][0]["id"] and t["is_current_round"] for t in p["tasks"])
    old_task_ids = {t["id"] for t in p["tasks"]}
    r1_id = p["rounds"][0]["id"]

    # noch nicht abgeschlossen -> kein Folgeauftrag
    r = client.post(f"/api/projects/{p['id']}/follow-up", json={"title": "Planänderung 2026"})
    assert r.status_code == 409 and "abgeschlossen" in r.json()["detail"]
    # Status muss anfrage oder angebot sein
    r = client.post(f"/api/projects/{p['id']}/follow-up", json={"title": "X", "status": "beauftragt"})
    assert r.status_code == 422

    # eine alte Aufgabe bleibt offen und überfällig liegen, das Projekt wird abgeschlossen (behalten)
    client.put(f"/api/tasks/{p['tasks'][0]['id']}", json={"due_date": "2026-01-15"})
    p = client.post(f"/api/projects/{p['id']}/complete", json={"open_tasks": "behalten"}).json()
    assert p["status"] == "abgeschlossen" and p["rounds"][0]["status"] == "abgeschlossen"

    # Folgeauftrag mit Vorlage
    p = client.post(f"/api/projects/{p['id']}/follow-up", json={"title": "Planänderung 2026", "request_date": "2026-10-01", "template_id": tpl}).json()
    assert p["round_number"] == 2 and p["round_title"] == "Planänderung 2026" and p["status"] == "anfrage"
    assert p["request_date"] == "2026-10-01" and p["order_date"] is None and p["completed_at"] is None
    assert len(p["rounds"]) == 2 and p["rounds"][0]["closed_at"] is not None and p["rounds"][1]["number"] == 2
    new_tasks = [t for t in p["tasks"] if t["id"] not in old_task_ids]
    assert new_tasks and all(t["round_id"] == p["rounds"][1]["id"] and t["is_current_round"] for t in new_tasks)
    assert all(not t["is_current_round"] and t["round_number"] == 1 for t in p["tasks"] if t["id"] in old_task_ids)
    # Fortschritt und Ampel ignorieren die alte Runde: keine überfällige Aufgabe, nicht aktiv -> grau, Fortschritt 0
    assert p["signal"] == "grau" and p["overdue_count"] == 0 and p["progress"] == 0
    assert p["task_count"] == len(new_tasks) and p["rounds"][0]["task_count"] == len(old_task_ids)
    assert any(a["action"] == "Folgeauftrag gestartet" and a["new_value"] == "2" for a in client.get(f"/api/projects/{p['id']}/activity").json())

    # Auftragsdatum -> beauftragt, Runde 2 spiegelt das
    p = client.put(f"/api/projects/{p['id']}", json={"order_date": "2026-10-05", "offered_weeks": 3}).json()
    assert p["status"] == "beauftragt" and p["rounds"][1]["status"] == "beauftragt" and p["rounds"][1]["order_date"] == "2026-10-05"
    assert p["rounds"][0]["status"] == "abgeschlossen"
    assert p["is_active"] and p["signal"] in ("gruen", "gelb") and p["overdue_count"] == 0

    # alte Aufgaben tauchen in Tagesansichten, Aufgabenliste, Kalender und Zeitplan nicht auf
    d = client.get("/api/dashboard").json()
    shown = {t["id"] for lst in (d["today_tasks"], d["overdue_tasks"], d["upcoming"], d["waiting"]) for t in lst}
    assert not shown & old_task_ids
    assert not {t["id"] for t in client.get("/api/tasks", params={"open_only": "true"}).json()} & old_task_ids
    assert not {t["id"] for t in client.get("/api/tasks", params={"bucket": "ueberfaellig"}).json()} & old_task_ids
    cal = client.get("/api/calendar", params={"start": "2026-01-01", "end": "2026-12-31"}).json()
    assert not {t["id"] for day in cal for t in day["tasks"]} & old_task_ids
    sched = client.get("/api/schedule", params={"project_id": p["id"], "include_done": "true"}).json()
    assert not {t["id"] for sp in sched["projects"] for t in sp["tasks"]} & old_task_ids
    # Projektliste zeigt die Runde
    lst = client.get("/api/projects").json()
    assert [o["round_number"] for o in lst if o["id"] == p["id"]] == [2]

    # Erwarteter Ordnername ab Runde 2 immer Auftrag, auch im Status Anfrage: kein Hinweis
    p2 = client.put(f"/api/projects/{p['id']}", json={"status": "anfrage"}).json()
    assert p2["expected_folder_name"] == "26-600 Auftrag Erst" and p2["folder_matches"] is True and p2["folder_note"] is None

    # Export mit Spalte Runde
    csv_text = client.get("/api/export/csv", params={"what": "projects"}).text
    assert csv_text.splitlines()[0].endswith(";Runde") and csv_text.splitlines()[1].endswith(";2")

    # NAS unverändert
    assert _tree(base) == before
