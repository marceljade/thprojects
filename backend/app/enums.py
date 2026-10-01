"""Feste Wertelisten. Status und Priorität sind bewusst im Code, weil die
Fälligkeits- und Ampellogik von ihnen abhängt. Beschriftungen liefert /api/meta."""
from __future__ import annotations

from enum import Enum


class ProjectStatus(str, Enum):
    anfrage = "anfrage"
    angebot = "angebot"
    beauftragt = "beauftragt"
    in_bearbeitung = "in_bearbeitung"
    wartet_kunde = "wartet_kunde"
    interne_pruefung = "interne_pruefung"
    abgeschlossen = "abgeschlossen"
    auf_eis = "auf_eis"
    abgelehnt = "abgelehnt"


PROJECT_STATUS_LABELS = {
    ProjectStatus.anfrage: "Anfrage",
    ProjectStatus.angebot: "Angebot erstellt",
    ProjectStatus.beauftragt: "Beauftragt",
    ProjectStatus.in_bearbeitung: "In Bearbeitung",
    ProjectStatus.wartet_kunde: "Wartet auf Kunde",
    ProjectStatus.interne_pruefung: "Interne Prüfung",
    ProjectStatus.abgeschlossen: "Abgeschlossen",
    ProjectStatus.auf_eis: "Auf Eis",
    ProjectStatus.abgelehnt: "Abgelehnt / storniert",
}

ACTIVE_PROJECT_STATUSES = {
    ProjectStatus.beauftragt,
    ProjectStatus.in_bearbeitung,
    ProjectStatus.wartet_kunde,
    ProjectStatus.interne_pruefung,
}
CLOSED_PROJECT_STATUSES = {ProjectStatus.abgeschlossen, ProjectStatus.abgelehnt}


class TaskStatus(str, Enum):
    nicht_begonnen = "nicht_begonnen"
    geplant = "geplant"
    in_bearbeitung = "in_bearbeitung"
    wartet = "wartet"
    erledigt = "erledigt"
    entfaellt = "entfaellt"


TASK_STATUS_LABELS = {
    TaskStatus.nicht_begonnen: "Nicht begonnen",
    TaskStatus.geplant: "Geplant",
    TaskStatus.in_bearbeitung: "In Bearbeitung",
    TaskStatus.wartet: "Wartet auf Rückmeldung",
    TaskStatus.erledigt: "Erledigt",
    TaskStatus.entfaellt: "Entfällt",
}

OPEN_TASK_STATUSES = {TaskStatus.nicht_begonnen, TaskStatus.geplant, TaskStatus.in_bearbeitung, TaskStatus.wartet}


class Priority(str, Enum):
    niedrig = "niedrig"
    normal = "normal"
    hoch = "hoch"
    kritisch = "kritisch"


PRIORITY_LABELS = {
    Priority.niedrig: "Niedrig",
    Priority.normal: "Normal",
    Priority.hoch: "Hoch",
    Priority.kritisch: "Kritisch",
}
PRIORITY_RANK = {Priority.kritisch: 0, Priority.hoch: 1, Priority.normal: 2, Priority.niedrig: 3}


class ProjectCategory(str, Enum):
    wea = "wea"                # WEA-Vermessung (Windpark: Messung, erste Ergebnisse, Berichte)
    messung = "messung"        # Messung vor Ort (Immission, Nachhall, Bauakustik)
    gutachten = "gutachten"    # Prognose / Gutachten ohne eigene Messung
    intern = "intern"          # QM, DAkkS, interne Vorgänge


PROJECT_CATEGORY_LABELS = {
    ProjectCategory.wea: "WEA-Vermessung",
    ProjectCategory.messung: "Messung",
    ProjectCategory.gutachten: "Gutachten / Prognose",
    ProjectCategory.intern: "Intern",
}


class DueState(str, Enum):
    erledigt = "erledigt"
    ohne_frist = "ohne_frist"
    ueberfaellig = "ueberfaellig"
    heute = "heute"
    demnaechst = "demnaechst"
    woche = "woche"
    spaeter = "spaeter"


DUE_STATE_LABELS = {
    DueState.erledigt: "Erledigt",
    DueState.ohne_frist: "Ohne Frist",
    DueState.ueberfaellig: "Überfällig",
    DueState.heute: "Heute",
    DueState.demnaechst: "Demnächst",
    DueState.woche: "Diese Woche",
    DueState.spaeter: "Später",
}
DUE_STATE_RANK = {
    DueState.ueberfaellig: 0, DueState.heute: 1, DueState.demnaechst: 2, DueState.woche: 3,
    DueState.spaeter: 4, DueState.ohne_frist: 5, DueState.erledigt: 6,
}


class Signal(str, Enum):
    """Projekt-Ampel"""
    rot = "rot"
    gelb = "gelb"
    gruen = "gruen"
    grau = "grau"      # nicht aktiv (Anfrage, Angebot, Auf Eis)
    fertig = "fertig"  # abgeschlossen / abgelehnt
