"""Outlook-Anbindung ohne Outlook: reine Soll-Funktion und Abgleich gegen einen Fake-Kalender."""
from datetime import date
from types import SimpleNamespace as NS

from app.services import outlook
from app.services.outlook import Entry, Event, clear_calendar, desired_events, sync_calendar


class FakeCalendar:
    """Merkt sich Termine wie Outlook: Einträge mit pmth_id und fremde Einträge ohne."""

    def __init__(self):
        self.items: dict[int, dict] = {}
        self._n = 0
        self.ops: list[str] = []

    def put(self, key, subject, day, high):
        self._n += 1
        self.items[self._n] = {"key": key, "subject": subject, "day": day, "high": high}
        return self._n

    def list(self):
        return [Entry(v["key"], v["subject"], v["day"], v["high"], handle=k) for k, v in self.items.items() if v["key"]]

    def add(self, ev: Event):
        self.ops.append(f"add {ev.key}")
        self.put(ev.key, ev.subject, ev.day, ev.high)

    def update(self, handle, ev: Event):
        self.ops.append(f"update {ev.key}")
        self.items[handle].update(subject=ev.subject, day=ev.day, high=ev.high)

    def delete(self, handle):
        self.ops.append(f"delete {self.items[handle]['key']}")
        del self.items[handle]

    def keys(self):
        return sorted(v["key"] for v in self.items.values() if v["key"])


def _task(i, due, status="nicht_begonnen", prio="normal", current=True, nr="26-001", name="BESS Test", title="Bericht"):
    return NS(id=i, due_date=due, is_open=status not in ("erledigt", "entfaellt"), status=status, priority=prio,
              is_current_round=current, project_number=nr, project_name=name, title=title)


def _project(i, deadline, active=True, prio="normal", nr="26-001", name="BESS Test"):
    return NS(id=i, deadline=deadline, is_active=active, priority=prio, project_number=nr, name=name)


def test_desired_events():
    tasks = [_task(1, date(2026, 10, 9), prio="hoch"), _task(2, None), _task(3, date(2026, 10, 10), status="erledigt"),
             _task(4, date(2026, 10, 11), status="entfaellt"), _task(5, date(2026, 10, 8), current=False), _task(6, date(2026, 10, 12), status="wartet")]
    projects = [_project(1, date(2026, 10, 30), prio="kritisch"), _project(2, date(2026, 11, 1), active=False), _project(3, None)]
    ev = desired_events(projects, tasks)
    assert [e.key for e in ev] == ["task:1", "task:6", "project:1"]
    assert ev[0] == Event("task:1", "26-001 BESS Test: Bericht", date(2026, 10, 9), True)
    assert ev[1].high is False
    assert ev[2] == Event("project:1", "26-001 BESS Test: Projektfrist", date(2026, 10, 30), True)


def test_sync_create_update_remove_idempotent():
    cal = FakeCalendar()
    foreign = cal.put("", "Zahnarzt", date(2026, 10, 9), False)      # fremder Termin ohne pmth_id
    cal.put("task:9", "26-001 Alt: Weg", date(2026, 1, 1), False)     # zu einer inzwischen erledigten Aufgabe
    cal.put("task:1", "26-001 BESS Test: Bericht", date(2026, 10, 1), False)   # Datum und Kategorie veraltet
    desired = [Event("task:1", "26-001 BESS Test: Bericht", date(2026, 10, 9), True),
               Event("project:1", "26-001 BESS Test: Projektfrist", date(2026, 10, 30), False)]
    r = sync_calendar(cal, desired)
    assert (r.created, r.updated, r.removed, r.total) == (1, 1, 1, 2)
    assert cal.keys() == ["project:1", "task:1"]
    assert foreign in cal.items and cal.items[foreign]["subject"] == "Zahnarzt"
    assert [v for v in cal.items.values() if v["key"] == "task:1"][0] == {"key": "task:1", "subject": "26-001 BESS Test: Bericht", "day": date(2026, 10, 9), "high": True}
    assert "angelegt" in r.message and "geändert" in r.message and "entfernt" in r.message

    # zweiter Lauf: nichts passiert
    cal.ops.clear()
    r2 = sync_calendar(cal, desired)
    assert (r2.created, r2.updated, r2.removed) == (0, 0, 0) and cal.ops == []

    # Doppelgänger mit gleicher Kennung werden auf einen reduziert
    cal.put("task:1", "Doppelt", date(2026, 10, 9), True)
    r3 = sync_calendar(cal, desired)
    assert r3.removed == 1 and cal.keys() == ["project:1", "task:1"]

    # leeren entfernt nur eigene Termine
    assert clear_calendar(cal) == 2
    assert list(cal.items) == [foreign]


def test_sync_via_api(client, monkeypatch):
    """Route, Einstellung und Protokoll, Outlook durch den Fake ersetzt."""
    cal = FakeCalendar()
    monkeypatch.setattr(outlook, "open_calendar", lambda: cal)
    r = client.put("/api/settings", json={"outlook_sync": "unsinn"})
    assert r.status_code == 422
    r = client.put("/api/settings", json={"outlook_sync": "manuell"}).json()
    assert r["outlook_sync"] == "manuell" and r["outlook_last_sync"] is None

    p = client.post("/api/projects", json={"project_number": "26-700", "name": "Sync", "status": "in_bearbeitung",
                                           "order_date": "2026-10-01", "offered_weeks": 4, "priority": "hoch"}).json()
    t1 = client.post("/api/tasks", json={"project_id": p["id"], "title": "Bericht", "due_date": "2026-10-09", "priority": "hoch"}).json()
    client.post("/api/tasks", json={"project_id": p["id"], "title": "Ohne Frist"})
    r = client.post("/api/outlook/sync").json()
    assert (r["created"], r["updated"], r["removed"], r["total"]) == (2, 0, 0, 2)
    assert cal.keys() == [f"project:{p['id']}", f"task:{t1['id']}"]
    ev = [v for v in cal.items.values() if v["key"] == f"task:{t1['id']}"][0]
    assert ev == {"key": f"task:{t1['id']}", "subject": "26-700 Sync: Bericht", "day": date(2026, 10, 9), "high": True}
    s = client.get("/api/settings").json()
    assert s["outlook_last_sync"] is not None and s["outlook_last_result"].startswith("2 angelegt")
    assert any(a["action"] == "Outlook-Abgleich" for a in client.get("/api/activity").json())

    # Aufgabe erledigt -> Termin verschwindet, Projekt abgeschlossen -> Projektfrist verschwindet
    client.post(f"/api/tasks/{t1['id']}/complete")
    assert client.post("/api/outlook/sync").json()["removed"] == 1
    client.post(f"/api/projects/{p['id']}/complete", json={"open_tasks": "erledigt"})
    assert client.post("/api/outlook/sync").json()["removed"] == 1 and cal.keys() == []

    # leeren
    cal.put("task:999", "Rest", date(2026, 1, 1), False)
    assert client.post("/api/outlook/clear").json()["removed"] == 1

    # Fehler aus dem Adapter kommen als 503 mit Text an und landen im Protokoll
    def boom():
        raise outlook.OutlookError("Outlook ist nicht erreichbar (Test).")
    monkeypatch.setattr(outlook, "open_calendar", boom)
    r = client.post("/api/outlook/sync")
    assert r.status_code == 503 and "nicht erreichbar" in r.json()["detail"]
    assert any(a["action"] == "Outlook-Fehler" for a in client.get("/api/activity").json())
    assert client.get("/api/settings").json()["outlook_last_result"].startswith("Outlook ist nicht erreichbar")


def test_com_messages():
    class E(Exception):
        def __init__(self, hresult):
            super().__init__(hresult)
            self.hresult = hresult
    assert "nicht installiert" in outlook._com_message(E(-2147221005))
    assert "abgelehnt" in outlook._com_message(E(-2147467260))
    assert "nicht erreichbar" in outlook._com_message(E(-1))
