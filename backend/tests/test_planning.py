"""Geplant am (planned_date) neben der Frist: Kalendertag, Heute-Logik, Warnungen, Migration, Drag-and-Drop-Route."""
from datetime import date

from app import scheduling as s
from app.enums import TaskStatus

T = date(2026, 10, 7)   # Mittwoch


def test_calendar_day_and_warnings():
    assert s.calendar_day(None, None) is None
    assert s.calendar_day(None, date(2026, 10, 9)) == date(2026, 10, 9)
    assert s.calendar_day(date(2026, 10, 8), date(2026, 10, 9)) == date(2026, 10, 8)
    assert s.planned_after_due(date(2026, 10, 10), date(2026, 10, 9)) is True
    assert s.planned_after_due(date(2026, 10, 9), date(2026, 10, 9)) is False
    assert s.planned_after_due(date(2026, 10, 10), None) is False
    assert s.task_warnings(TaskStatus.nicht_begonnen, date(2026, 10, 10), date(2026, 10, 9), T) == ["nach Frist geplant"]
    assert s.task_warnings(TaskStatus.in_bearbeitung, date(2026, 10, 5), None, T) == ["geplant für Montag"]
    assert s.task_warnings(TaskStatus.geplant, date(2026, 10, 6), date(2026, 10, 2), T) == ["nach Frist geplant", "geplant für Dienstag"]
    assert s.task_warnings(TaskStatus.erledigt, date(2026, 10, 10), date(2026, 10, 9), T) == []
    assert s.task_warnings(TaskStatus.nicht_begonnen, T, date(2026, 10, 9), T) == []


def test_is_today():
    today = T
    # Frist heute, geplant heute, liegen geblieben
    assert s.is_today(TaskStatus.nicht_begonnen, None, today, today)
    assert s.is_today(TaskStatus.nicht_begonnen, today, date(2026, 10, 20), today)
    assert s.is_today(TaskStatus.nicht_begonnen, date(2026, 10, 5), None, today)
    assert s.is_today(TaskStatus.wartet, date(2026, 10, 5), date(2026, 10, 20), today)
    # nicht heute: morgen geplant, Frist morgen, erledigt, überfällig (gehört nur zu Überfällig)
    assert not s.is_today(TaskStatus.nicht_begonnen, date(2026, 10, 8), None, today)
    assert not s.is_today(TaskStatus.nicht_begonnen, None, date(2026, 10, 8), today)
    assert not s.is_today(TaskStatus.erledigt, today, today, today)
    assert not s.is_today(TaskStatus.nicht_begonnen, today, date(2026, 10, 1), today)
    assert not s.is_today(TaskStatus.nicht_begonnen, None, None, today)


def test_migration_adds_planned_date(tmp_path):
    import sqlite3
    from sqlalchemy import create_engine
    from app.migrate import migrate
    db = tmp_path / "alt.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, project_number TEXT, name TEXT)")
    con.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, project_id INTEGER, title TEXT, due_date DATE)")
    con.execute("INSERT INTO projects (project_number, name) VALUES ('25-001', 'Alt')")
    con.execute("INSERT INTO tasks (project_id, title, due_date) VALUES (1, 'A', '2026-10-09')")
    con.commit(); con.close()
    assert "tasks.planned_date" in migrate(create_engine(f"sqlite:///{db}"))
    con = sqlite3.connect(db)
    assert con.execute("SELECT planned_date, due_date FROM tasks").fetchone() == (None, "2026-10-09")
    con.close()


def test_plan_via_api(client):
    today = date.today()
    iso = lambda d: d.isoformat()  # noqa: E731
    from datetime import timedelta
    p = client.post("/api/projects", json={"project_number": "26-800", "name": "Plan", "status": "in_bearbeitung",
                                           "order_date": iso(today), "offered_weeks": 4}).json()
    due = today + timedelta(days=7)
    t = client.post("/api/tasks", json={"project_id": p["id"], "title": "Bericht", "due_date": iso(due)}).json()
    u = client.post("/api/tasks", json={"project_id": p["id"], "title": "Ohne alles", "priority": "hoch"}).json()
    w = client.post("/api/tasks", json={"project_id": p["id"], "title": "Wartet", "status": "wartet", "waiting_on": "AG"}).json()
    assert t["planned_date"] is None and t["calendar_date"] == iso(due) and t["is_today"] is False

    # Ungeplant: ohne Frist, ohne Plantag, nicht wartend
    ids = [x["id"] for x in client.get("/api/calendar/unplanned").json()]
    assert u["id"] in ids and t["id"] not in ids and w["id"] not in ids

    # Drag and Drop: nur planned_date ändert sich, Protokoll mit Details
    r = client.put(f"/api/tasks/{t['id']}/plan", json={"planned_date": iso(today)}).json()
    assert r["planned_date"] == iso(today) and r["due_date"] == iso(due) and r["calendar_date"] == iso(today) and r["is_today"]
    acts = client.get(f"/api/projects/{p['id']}/activity").json()
    a = next(a for a in acts if a["action"] == "Aufgabe geplant")
    assert a["details"] == f"geplant am – -> {today.strftime('%d.%m.')}" and a["field"] == "planned_date"

    # Kalender: Aufgabe am Plantag, Fristmarkierung am Fristtag, Projektfrist als Markierung
    cal = {d["date"]: d for d in client.get("/api/calendar", params={"start": iso(today), "end": iso(today + timedelta(days=30))}).json()}
    assert [x["id"] for x in cal[iso(today)]["tasks"]] == [t["id"]]
    assert cal[iso(due)]["tasks"] == [] and [(m["kind"], m["task_id"]) for m in cal[iso(due)]["marks"]] == [("due", t["id"])]
    assert any(m["kind"] == "project" and m["project_id"] == p["id"] for m in cal[iso(today + timedelta(days=28))]["marks"])

    # Dashboard Heute und Bucket heute
    d = client.get("/api/dashboard").json()
    assert t["id"] in [x["id"] for x in d["today_tasks"]] and d["counts"]["today"] >= 1
    assert t["id"] in [x["id"] for x in client.get("/api/tasks", params={"bucket": "heute"}).json()]

    # nach Frist geplant -> Warnung, nicht blockiert
    r = client.put(f"/api/tasks/{t['id']}/plan", json={"planned_date": iso(due + timedelta(days=1))}).json()
    assert r["planned_after_due"] is True and r["warnings"] == ["nach Frist geplant"]
    # liegen geblieben -> Hinweis mit Wochentag und heute
    r = client.put(f"/api/tasks/{t['id']}/plan", json={"planned_date": iso(today - timedelta(days=1))}).json()
    assert r["is_today"] and r["warnings"] == [f"geplant für {s.WEEKDAYS_DE[(today - timedelta(days=1)).weekday()]}"]
    # überfällige Frist: nicht bei Heute, auch wenn heute geplant
    r = client.put(f"/api/tasks/{t['id']}", json={"due_date": iso(today - timedelta(days=2)), "planned_date": iso(today)}).json()
    assert r["due_state"] == "ueberfaellig" and r["is_today"] is False
    d = client.get("/api/dashboard").json()
    assert t["id"] in [x["id"] for x in d["overdue_tasks"]] and t["id"] not in [x["id"] for x in d["today_tasks"]]

    # zurück in die Leiste: planned_date leeren, über Dialog-Update mit clear ebenfalls möglich
    r = client.put(f"/api/tasks/{t['id']}/plan", json={"planned_date": None}).json()
    assert r["planned_date"] is None and r["calendar_date"] == iso(today - timedelta(days=2))
    r = client.put(f"/api/tasks/{u['id']}", json={"planned_date": iso(today)}).json()
    assert r["planned_date"] == iso(today)
    r = client.put(f"/api/tasks/{u['id']}", json={"clear": ["planned_date"]}).json()
    assert r["planned_date"] is None

    # erledigte Aufgabe lässt sich nicht planen
    client.post(f"/api/tasks/{t['id']}/complete")
    assert client.put(f"/api/tasks/{t['id']}/plan", json={"planned_date": iso(today)}).status_code == 409
    # Export hat die Spalte
    assert client.get("/api/export/csv", params={"what": "tasks"}).text.splitlines()[0].endswith(";Geplant am")
