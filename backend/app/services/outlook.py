"""Fristen in einen eigenen Outlook-Kalender schreiben. Einweg: App -> Outlook.

Drei Schichten, damit nichts davon Outlook braucht, außer dem Adapter ganz unten:
  desired_events()   reine Funktion: was soll im Kalender stehen (aus den fertigen DTOs, nichts neu gerechnet)
  sync_calendar()    reiner Abgleich gegen einen Kalender mit list/add/update/delete (im Test ein Fake)
  OutlookCalendar    der echte Adapter über pywin32, win32com wird erst in den Methoden importiert

Invariante 12: Die App schreibt, ändert und löscht ausschließlich im Ordner "Projektfristen" unter dem
Standardkalender und dort nur Termine mit der eigenen Kennung pmthid. Alles andere wird nie angefasst.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session

from .. import models
from ..enums import Priority
from ..schemas import OutlookSyncOut, ProjectOut, TaskOut
from . import common

FOLDER_NAME = "Projektfristen"
PROP = "pmthid"     # Outlook erlaubt in Feldnamen kein _ [ ] #
CATEGORY = "Projektfristen"       # eigene Kategorie in Rot, wird einmalig in der Kategorienliste des Postfachs angelegt
AUTO_DELAY_SECONDS = 5

SYNC_MODES = ("aus", "manuell", "automatisch")


class OutlookError(Exception):
    """Fehlermeldung in der Stimme der App, mit dem nächsten Schritt für den Nutzer."""


# ------------------------------------------------------------------- Soll --
@dataclass(frozen=True)
class Event:
    key: str        # "task:123" oder "project:45"
    subject: str
    day: date
    high: bool      # rote Kategorie


def _high(priority) -> bool:
    return Priority(priority) in (Priority.hoch, Priority.kritisch)


def desired_events(projects: list[ProjectOut], tasks: list[TaskOut]) -> list[Event]:
    """Was im Kalender stehen soll. Offene Aufgaben mit Frist (aktuelle Runde) und Projektfristen aktiver Projekte."""
    out: list[Event] = []
    for t in tasks:
        if not t.is_open or t.due_date is None or not getattr(t, "is_current_round", True):
            continue
        out.append(Event(f"task:{t.id}", f"{t.project_number} {t.project_name}: {t.title}", t.due_date, _high(t.priority)))
    for p in projects:
        if not p.is_active or p.deadline is None:
            continue
        out.append(Event(f"project:{p.id}", f"{p.project_number} {p.name}: Projektfrist", p.deadline, _high(p.priority)))
    out.sort(key=lambda e: (e.day, e.key))
    return out


# --------------------------------------------------------------- Abgleich --
@dataclass
class Entry:
    key: str
    subject: str
    day: date
    high: bool
    handle: Any     # beliebiges Objekt des Kalenders, wird bei update/delete zurückgegeben


class CalendarPort(Protocol):
    def list(self) -> list[Entry]: ...          # nur Einträge mit pmth_id
    def add(self, ev: Event) -> None: ...
    def update(self, handle: Any, ev: Event) -> None: ...
    def delete(self, handle: Any) -> None: ...


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    removed: int = 0
    total: int = 0

    @property
    def message(self) -> str:
        return f"{self.created} angelegt, {self.updated} geändert, {self.removed} entfernt, {self.total} Termine im Kalender"


def sync_calendar(cal: CalendarPort, desired: list[Event]) -> SyncResult:
    """Idempotent: fehlende anlegen, abweichende aktualisieren, überzählige entfernen. Zweimal laufen = keine Änderung."""
    r = SyncResult()
    want = {e.key: e for e in desired}
    seen: set[str] = set()
    for entry in cal.list():
        ev = want.get(entry.key)
        if ev is None or entry.key in seen:
            cal.delete(entry.handle)       # Aufgabe erledigt/entfallen/gelöscht/ohne Frist, oder Doppelgänger
            r.removed += 1
            continue
        seen.add(entry.key)
        if (entry.subject, entry.day, entry.high) != (ev.subject, ev.day, ev.high):
            cal.update(entry.handle, ev)
            r.updated += 1
    for key, ev in want.items():
        if key not in seen:
            cal.add(ev)
            r.created += 1
    r.total = len(want)
    return r


def clear_calendar(cal: CalendarPort) -> int:
    n = 0
    for entry in cal.list():
        cal.delete(entry.handle)
        n += 1
    return n


# ---------------------------------------------------------- Outlook-Adapter --
class OutlookCalendar:
    """Ordner "Projektfristen" unter dem Standardkalender des Standardpostfachs. Legt ihn beim ersten Mal an."""

    def __init__(self) -> None:
        self._folder = None
        self._red = CATEGORY

    def open(self) -> "OutlookCalendar":
        try:
            import pythoncom  # noqa: F401
            import win32com.client
        except ImportError as e:
            raise OutlookError("Die Outlook-Anbindung fehlt: pywin32 ist nicht installiert. Starte die App einmal über start.bat neu, "
                               "dann wird es nachinstalliert.") from e
        import pywintypes
        try:
            pythoncom.CoInitialize()
            app = win32com.client.Dispatch("Outlook.Application")
            ns = app.GetNamespace("MAPI")
            root = ns.GetDefaultFolder(9)   # olFolderCalendar
        except pywintypes.com_error as e:  # noqa: PERF203
            raise OutlookError(_com_message(e)) from e
        try:
            folder = None
            for i in range(root.Folders.Count):
                f = root.Folders.Item(i + 1)
                if f.Name == FOLDER_NAME:
                    folder = f
                    break
            if folder is None:
                folder = root.Folders.Add(FOLDER_NAME, 9)
            self._folder = folder
            try:
                # Eigene rote Kategorie, damit keine vorhandene Kategorie des Nutzers mitbenutzt wird
                if not any(ns.Categories.Item(i + 1).Name == CATEGORY for i in range(ns.Categories.Count)):
                    ns.Categories.Add(CATEGORY, 1)   # olCategoryColorRed
            except pywintypes.com_error:
                pass
        except pywintypes.com_error as e:
            raise OutlookError(_com_message(e)) from e
        return self

    def _items(self):
        items = self._folder.Items
        items.IncludeRecurrences = False
        return items

    def list(self) -> list[Entry]:
        out: list[Entry] = []
        items = self._items()
        for i in range(items.Count, 0, -1):     # rückwärts, damit Löschen die Indizes nicht verschiebt
            it = items.Item(i)
            try:
                prop = it.UserProperties.Find(PROP)
            except Exception:  # noqa: BLE001
                prop = None
            if prop is None or not prop.Value:
                continue
            start = it.Start.astimezone()   # pywin32 liefert UTC, der Fristtag gilt in lokaler Zeit
            out.append(Entry(key=str(prop.Value), subject=str(it.Subject or ""), day=date(start.year, start.month, start.day),
                             high=self._red in str(it.Categories or "").split(", "), handle=it))
        return out

    def _fill(self, it, ev: Event) -> None:
        it.Subject = ev.subject
        it.AllDayEvent = True
        it.Start = datetime(ev.day.year, ev.day.month, ev.day.day)
        it.End = datetime(ev.day.year, ev.day.month, ev.day.day) + timedelta(days=1)
        it.ReminderSet = False
        it.BusyStatus = 0       # olFree
        it.Categories = self._red if ev.high else ""

    def add(self, ev: Event) -> None:
        it = self._items().Add(1)   # olAppointmentItem
        self._fill(it, ev)
        it.UserProperties.Add(PROP, 1).Value = ev.key   # olText
        it.Save()

    def update(self, handle: Any, ev: Event) -> None:
        self._fill(handle, ev)
        handle.Save()

    def delete(self, handle: Any) -> None:
        handle.Delete()


def _com_message(e: Exception) -> str:
    code = getattr(e, "hresult", None) or (e.args[0] if e.args else None)
    if code in (-2147221005, -2147221164):   # CO_E_CLASSSTRING, REGDB_E_CLASSNOTREG
        return ("Das klassische Outlook ist auf diesem Rechner nicht installiert oder nicht als COM-Anwendung registriert. "
                "Outlook (Microsoft 365, klassische Ansicht) installieren und einmal starten, dann noch einmal abgleichen.")
    if code in (-2147467260, -2147352567):   # E_ABORT, DISP_E_EXCEPTION (häufig die Sicherheitsabfrage)
        return ("Outlook hat den Zugriff abgelehnt, meist über die Sicherheitsabfrage. In Outlook die Abfrage mit „Zulassen“ bestätigen "
                "oder unter Datei > Optionen > Trust Center > Programmgesteuerter Zugriff die Warnung erlauben, dann noch einmal abgleichen.")
    return (f"Outlook ist nicht erreichbar ({e}). Outlook einmal starten und das Postfach öffnen, dann noch einmal abgleichen. "
            "Läuft die App als anderer Benutzer als Outlook, geht der Zugriff nicht.")


def open_calendar() -> CalendarPort:
    """Wird im Test durch einen Fake ersetzt (monkeypatch)."""
    return OutlookCalendar().open()


# ----------------------------------------------------------------- Service --
def desired_from_db(db: Session) -> list[Event]:
    from . import tasks as tasks_service
    p = common.params(db)
    projects = [common.project_out(pr, p) for pr in common.load_projects(db)]
    tasks = tasks_service.list_tasks(db, open_only=True)
    return desired_events(projects, tasks)


def sync_mode(db: Session) -> str:
    v = common.get_setting(db, "outlook_sync", "aus")
    return v if v in SYNC_MODES else "aus"


def _record(db: Session, result: SyncResult | None, error: str | None, manual: bool) -> None:
    now = datetime.now()
    common.set_setting(db, "outlook_last_sync", now.isoformat(timespec="seconds"))
    common.set_setting(db, "outlook_last_result", error or (result.message if result else ""))
    if error:
        common.log(db, "Outlook-Fehler", details=error)
    elif manual:
        common.log(db, "Outlook-Abgleich", details=result.message)
    db.commit()


def run_sync(db: Session, manual: bool = True) -> OutlookSyncOut:
    """Abgleich ausführen. Fehler werden festgehalten und als OutlookError weitergegeben."""
    try:
        desired = desired_from_db(db)
        result = sync_calendar(open_calendar(), desired)
    except OutlookError as e:
        _record(db, None, str(e), manual)
        raise
    except Exception as e:  # noqa: BLE001
        msg = f"Outlook-Abgleich abgebrochen: {e}"
        _record(db, None, msg, manual)
        raise OutlookError(msg) from e
    _record(db, result, None, manual)
    return OutlookSyncOut(created=result.created, updated=result.updated, removed=result.removed, total=result.total,
                          at=datetime.now(), message=result.message)


def clear(db: Session) -> OutlookSyncOut:
    try:
        n = clear_calendar(open_calendar())
    except OutlookError as e:
        _record(db, None, str(e), True)
        raise
    result = SyncResult(removed=n, total=0)
    common.set_setting(db, "outlook_last_sync", datetime.now().isoformat(timespec="seconds"))
    common.set_setting(db, "outlook_last_result", f"Kalender geleert, {n} Termine entfernt")
    common.log(db, "Outlook-Kalender geleert", details=f"{n} Termine entfernt")
    db.commit()
    return OutlookSyncOut(created=0, updated=0, removed=n, total=0, at=datetime.now(), message=f"{n} Termine entfernt")


# ------------------------------------------------------------- Automatik --
_timer: threading.Timer | None = None
_lock = threading.Lock()
_session_factory = None


def _auto_worker() -> None:
    """Läuft im Hintergrund mit eigener Session. Darf nie eine Ausnahme nach außen lassen."""
    if _session_factory is None:
        return
    try:
        with _session_factory() as db:
            if sync_mode(db) != "automatisch":
                return
            try:
                run_sync(db, manual=False)
            except OutlookError:
                pass    # ist bereits in Einstellungen und Protokoll festgehalten
    except Exception:  # noqa: BLE001
        pass


def schedule_auto(delay: float = AUTO_DELAY_SECONDS) -> None:
    """Abgleich gebündelt mit Verzögerung anstoßen. Mehrere Änderungen kurz hintereinander ergeben einen Lauf."""
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(delay, _auto_worker)
        _timer.daemon = True
        _timer.start()


_WATCHED = (models.Task, models.Project, models.ProjectRound)


def register(session_factory) -> None:
    """Session-Ereignisse: nach jedem Commit mit Änderungen an Aufgaben oder Projekten den Abgleich anstoßen,
    sofern die Automatik eingeschaltet ist. Ein Fehler hier darf keine Schreibaktion der App scheitern lassen."""
    global _session_factory
    from sqlalchemy import event
    _session_factory = session_factory

    @event.listens_for(session_factory, "before_flush")
    def _flag(session, _ctx, _instances):
        # Hier darf noch gelesen werden (im after_commit nicht mehr), deshalb die Einstellung schon jetzt prüfen
        if session.info.get("pmth_outlook"):
            return
        if any(isinstance(o, _WATCHED) for o in list(session.new) + list(session.dirty) + list(session.deleted)):
            try:
                session.info["pmth_outlook"] = common.get_setting(session, "outlook_sync", "aus") == "automatisch"
            except Exception:  # noqa: BLE001
                session.info["pmth_outlook"] = False

    @event.listens_for(session_factory, "after_commit")
    def _after(session):
        if session.info.pop("pmth_outlook", False):
            schedule_auto()


def start_auto_on_boot(db: Session) -> None:
    if sync_mode(db) == "automatisch":
        schedule_auto(delay=2)
