"""Projektordner: <Basispfad>\\20JJ\\<Projektnr> <Anfrage|Auftrag> <Projektname>

Phase "Anfrage" für Anfrage und Angebot, "Auftrag" ab Beauftragt. Die App liest nur:
Pfad erkennen, vorhandenen Ordner suchen, Ordner öffnen. Sie legt nie Ordner an und
benennt nie um, der Ablageort ist das NAS.
"""
from __future__ import annotations

import os
import platform
import re
from pathlib import Path

from sqlalchemy.orm import Session

from .. import models
from ..enums import ProjectStatus
from . import common

PHASE_ANFRAGE = "Anfrage"
PHASE_AUFTRAG = "Auftrag"
_ILLEGAL = re.compile(r'[\\/:*?"<>|]+')


def phase_for_status(status: ProjectStatus | str) -> str:
    return PHASE_ANFRAGE if ProjectStatus(status) in (ProjectStatus.anfrage, ProjectStatus.angebot) else PHASE_AUFTRAG


def sanitize(name: str) -> str:
    name = _ILLEGAL.sub(" ", name).strip().rstrip(".")
    return re.sub(r"\s+", " ", name)


def year_dir(project_number: str) -> str | None:
    return f"20{project_number[:2]}" if re.match(r"^\d{2}-", project_number) else None


def expected_folder_name(pr: models.Project) -> str:
    return sanitize(f"{pr.project_number} {phase_for_status(pr.status)} {pr.name}")


def base_path(db: Session) -> str:
    return common.get_setting(db, "base_path", "").strip().rstrip("\\/")


def expected_folder_path(db: Session, pr: models.Project) -> str | None:
    base = base_path(db)
    y = year_dir(pr.project_number)
    if not base or not y:
        return None
    return str(Path(base) / y / expected_folder_name(pr))


def current_path(pr: models.Project) -> str:
    p = (pr.folder_path or "").strip()
    if p.lower().startswith("file:///"):
        p = p[8:]
    return p


def folder_matches(pr: models.Project) -> bool:
    """Stimmt der hinterlegte Ordnername mit Nummer, Phase und Name überein?"""
    cur = current_path(pr)
    if not cur:
        return True
    return Path(cur).name == expected_folder_name(pr)


def phase_of_folder(path: str) -> str | None:
    name = Path(path).name
    m = re.match(r"^\S+\s+(Anfrage|Auftrag)\b", name)
    return m.group(1) if m else None


_FOLDER_NAME = re.compile(r"^(\d{2}-\d{3})\s+(Anfrage|Auftrag)\s+(.+?)\s*$")


def parse_folder_path(path: str) -> dict | None:
    """Liest Projektnummer, Name und Status aus einem Pfad nach dem Muster
    <Basis>/20JJ/<Nr> <Anfrage|Auftrag> <Name> (Backslash oder Slash). Reine Funktion,
    nur der letzte Pfadbestandteil zählt. Liefert None, wenn das Muster nicht passt."""
    p = (path or "").strip().strip('"')
    if p.lower().startswith("file:///"):
        p = p[8:]
    p = p.rstrip("\\/")
    name = re.split(r"[\\/]", p)[-1] if p else ""
    m = _FOLDER_NAME.match(name)
    if not m:
        return None
    nr, phase, title = m.groups()
    status = ProjectStatus.anfrage if phase == PHASE_ANFRAGE else ProjectStatus.beauftragt
    return {"project_number": nr, "name": title, "status": status.value}


def base_reachable_dir(db: Session, path: str) -> bool:
    """Liegt der Pfad unter dem Basispfad und ist der Jahresordner erreichbar? Dann darf neu gesucht werden."""
    base = base_path(db)
    if not base or not path.lower().startswith(base.lower()):
        return False
    try:
        return Path(path).parent.is_dir()
    except OSError:
        return False


def folder_hint(db: Session, pr: models.Project) -> str | None:
    """Hinweis für die Projektseite, wenn der Ordner fehlt oder vom erwarteten Namen abweicht.
    Nur Text, die App ändert auf dem NAS nichts."""
    cur = current_path(pr)
    expected = expected_folder_name(pr)
    if not cur:
        if not base_path(db) or not year_dir(pr.project_number):
            return None
        return f"Kein Ordner mit {pr.project_number} im Jahresordner gefunden. Lege ihn auf dem NAS an, die App übernimmt ihn dann."
    if Path(cur).name == expected:
        return None
    old_phase = phase_of_folder(cur)
    new_phase = phase_for_status(pr.status)
    if old_phase and old_phase != new_phase:
        return f"Ordner heißt noch {old_phase}. Benenne ihn auf dem NAS in {new_phase} um."
    return f"Ordnername weicht ab. Erwartet: {expected}."


def find_folder(db: Session, project_number: str) -> str | None:
    """Sucht <Basispfad>\\20JJ\\<Projektnr>* und liefert den ersten Treffer."""
    base = base_path(db)
    y = year_dir(project_number)
    if not base or not y:
        return None
    ydir = Path(base) / y
    try:
        if not ydir.is_dir():
            return None
        for entry in sorted(ydir.iterdir()):
            if entry.is_dir() and entry.name.startswith(project_number):
                return str(entry)
    except OSError:
        return None
    return None


def can_open_folders() -> bool:
    return platform.system() == "Windows"


def open_in_explorer(path: str) -> bool:
    if can_open_folders():
        os.startfile(path)  # type: ignore[attr-defined]
        return True
    return False
