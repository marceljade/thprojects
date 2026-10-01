"""Grunddaten beim ersten Start: Bearbeiter, Aufgabenarten, Vorlagen, Feiertage, Einstellungen.
Läuft nur, wenn die jeweilige Tabelle leer ist – vorhandene Daten werden nie überschrieben."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .enums import ProjectCategory
from .services.common import get_setting, set_setting

USERS = [
    ("MC", "Marcel Cording", "Projektleitung"), ("JH", "Jürgen Hünerberg", "Geschäftsführung"),
    ("PW", "", ""), ("DV", "", ""), ("BD", "", ""), ("JS", "", ""), ("PR", "", ""), ("MB", "", ""),
    ("VERW", "Verwaltung", "Rechnungsstellung"),
]

TASK_TYPES = [
    ("Angebot", 1), ("Auftrag", 1), ("Unterlagen", 1), ("Messung", 3), ("Auswertung", 3), ("Prognose / Berechnung", 4),
    ("Erste Ergebnisse", 2), ("Bericht", 5), ("Anhänge", 2), ("Korrektur", 3), ("Versand", 1), ("Rechnung", 2), ("Sonstiges", 1),
]

# (Vorlage, Beschreibung, Kategorie, [(Aufgabe, Aufgabenart, Offset AT vor Frist, Rolle, hängt von Vorgänger ab)])
TEMPLATES = [
    ("WEA-Vermessung", "Schalltechnische Vermessung von Windenergieanlagen: Messung, erste Ergebnisse, Berichte", ProjectCategory.wea, [
        ("Auftrag prüfen", "Auftrag", 40, "PL", False),
        ("Messplanung und Abstimmung mit Betreiber", "Unterlagen", 35, "PL", False),
        ("Messung vorbereiten (Geräte, Standorte)", "Messung", 30, "PL", False),
        ("Messung durchführen", "Messung", 25, "PL", True),
        ("Messdaten auswerten", "Auswertung", 18, "PL", True),
        ("Erste Ergebnisse versenden", "Erste Ergebnisse", 15, "PL", True),
        ("Bericht erstellen", "Bericht", 6, "PL", True),
        ("Anhänge erstellen", "Anhänge", 5, "PL", False),
        ("Korrektur (interne Kontrolle)", "Korrektur", 3, "PL", True),
        ("Bericht versenden", "Versand", 0, "PL", True),
        ("Rechnung stellen", "Rechnung", -3, "VERW", True),
    ]),
    ("Messung", "Messung vor Ort mit Auswertung und Bericht (Immission, Nachhall, Bauakustik)", ProjectCategory.messung, [
        ("Auftrag prüfen", "Auftrag", 25, "PL", False),
        ("Unterlagen anfordern", "Unterlagen", 23, "PL", False),
        ("Messtermin abstimmen", "Messung", 20, "PL", False),
        ("Messung durchführen", "Messung", 15, "PL", True),
        ("Messdaten auswerten", "Auswertung", 10, "PL", True),
        ("Bericht erstellen", "Bericht", 6, "PL", True),
        ("Anhänge erstellen", "Anhänge", 5, "PL", False),
        ("Korrektur (interne Kontrolle)", "Korrektur", 3, "PL", True),
        ("Bericht versenden", "Versand", 0, "PL", True),
        ("Rechnung stellen", "Rechnung", -3, "VERW", True),
    ]),
    ("Gutachten / Prognose", "Schallprognose oder Gutachten ohne eigene Messung", ProjectCategory.gutachten, [
        ("Auftrag prüfen", "Auftrag", 20, "PL", False),
        ("Unterlagen anfordern", "Unterlagen", 18, "PL", False),
        ("Berechnung / Prognose", "Prognose / Berechnung", 10, "PL", True),
        ("Bericht erstellen", "Bericht", 6, "PL", True),
        ("Anhänge erstellen", "Anhänge", 5, "PL", False),
        ("Korrektur (interne Kontrolle)", "Korrektur", 3, "PL", True),
        ("Bericht versenden", "Versand", 0, "PL", True),
        ("Rechnung stellen", "Rechnung", -3, "VERW", True),
    ]),
    ("Standard Schallgutachten", "Vollständiger Ablauf mit Messung und Prognose", ProjectCategory.gutachten, [
        ("Unterlagen prüfen", "Unterlagen", 30, "PL", False),
        ("Daten anfordern", "Unterlagen", 28, "PL", False),
        ("Messung", "Messung", 22, "PL", False),
        ("Messdaten auswerten", "Auswertung", 18, "PL", True),
        ("Prognose", "Prognose / Berechnung", 14, "PL", True),
        ("Berechnung", "Prognose / Berechnung", 10, "PL", True),
        ("Bericht", "Bericht", 6, "PL", True),
        ("Korrektur", "Korrektur", 3, "PL", True),
        ("Rechnung", "Rechnung", -3, "VERW", True),
    ]),
    ("Angebot", "Von der Anfrage bis zum Angebot, ohne Projektfrist", None, [
        ("Anfrage prüfen", "Angebot", None, "PL", False),
        ("Angebot erstellen", "Angebot", None, "PL", True),
    ]),
]

HOLIDAYS = [
    (date(2026, 1, 1), "Neujahr"), (date(2026, 4, 3), "Karfreitag"), (date(2026, 4, 6), "Ostermontag"), (date(2026, 5, 1), "Tag der Arbeit"),
    (date(2026, 5, 14), "Christi Himmelfahrt"), (date(2026, 5, 25), "Pfingstmontag"), (date(2026, 10, 3), "Tag der Deutschen Einheit"),
    (date(2026, 10, 31), "Reformationstag"), (date(2026, 12, 24), "Heiligabend"), (date(2026, 12, 25), "1. Weihnachtstag"),
    (date(2026, 12, 26), "2. Weihnachtstag"), (date(2026, 12, 31), "Silvester"),
    (date(2027, 1, 1), "Neujahr"), (date(2027, 3, 26), "Karfreitag"), (date(2027, 3, 29), "Ostermontag"), (date(2027, 5, 1), "Tag der Arbeit"),
    (date(2027, 5, 6), "Christi Himmelfahrt"), (date(2027, 5, 17), "Pfingstmontag"), (date(2027, 10, 3), "Tag der Deutschen Einheit"),
    (date(2027, 10, 31), "Reformationstag"), (date(2027, 12, 24), "Heiligabend"), (date(2027, 12, 25), "1. Weihnachtstag"),
    (date(2027, 12, 26), "2. Weihnachtstag"), (date(2027, 12, 31), "Silvester"),
]


def seed(db: Session) -> None:
    if db.scalar(select(models.User).limit(1)) is None:
        for i, (code, name, role) in enumerate(USERS):
            db.add(models.User(code=code, name=name, role=role, active=True, sort_order=i))
        db.flush()
    if db.scalar(select(models.TaskType).limit(1)) is None:
        for i, (name, w) in enumerate(TASK_TYPES):
            db.add(models.TaskType(name=name, default_weight=w, sort_order=i))
        db.flush()
    if db.scalar(select(models.ProjectTemplate).limit(1)) is None:
        types = {t.name: t.id for t in db.scalars(select(models.TaskType)).all()}
        for i, (name, desc, cat, tasks) in enumerate(TEMPLATES):
            tpl = models.ProjectTemplate(name=name, description=desc, category=cat, sort_order=i)
            for j, (title, ttype, off, role, dep) in enumerate(tasks, start=1):
                tpl.tasks.append(models.TemplateTask(sort_order=j, title=title, task_type_id=types.get(ttype), offset_workdays=off,
                                                     assignee_role=role, depends_on_previous=dep))
            db.add(tpl)
        db.flush()
    if db.scalar(select(models.Holiday).limit(1)) is None:
        for d, n in HOLIDAYS:
            db.add(models.Holiday(date=d, name=n))
        db.flush()
    if not get_setting(db, "my_user_id"):
        mc = db.scalar(select(models.User).where(models.User.code == "MC"))
        if mc:
            set_setting(db, "my_user_id", str(mc.id))
    if not get_setting(db, "base_path"):
        set_setting(db, "base_path", r"\\NAS\Netzwerk\TH-Ingenieure\projektbezogene Daten")
    for k, v in (("warn_workdays", "3"), ("warn_project_workdays", "5"), ("auto_backup", "1"), ("auto_create_folder", "1"), ("auto_rename_folder", "1")):
        if not get_setting(db, k):
            set_setting(db, k, v)
    db.commit()
