"""Projektordner: <Basispfad>\\20JJ\\<Projektnr> <Anfrage|Auftrag> <Projektname>

Phase "Anfrage" für Anfrage und Angebot, "Auftrag" ab Beauftragt. Beim Phasenwechsel wird
der vorhandene Ordner umbenannt (nur das Phasenwort, der restliche Name bleibt wie er ist).
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


def base_reachable(db: Session) -> bool:
    base = base_path(db)
    try:
        return bool(base) and Path(base).is_dir()
    except OSError:
        return False


def create_folder(db: Session, pr: models.Project) -> dict:
    """Legt den erwarteten Ordner an (inkl. Jahresordner). Liefert {ok, path, message}."""
    target = expected_folder_path(db, pr)
    if not target:
        return {"ok": False, "path": "", "message": "Basispfad fehlt oder Projektnummer hat nicht das Format JJ-NNN."}
    if not base_reachable(db):
        return {"ok": False, "path": target, "message": f"Basispfad nicht erreichbar: {base_path(db)}"}
    try:
        Path(target).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"ok": False, "path": target, "message": f"Ordner konnte nicht angelegt werden: {e}"}
    return {"ok": True, "path": target, "message": f"Ordner angelegt: {Path(target).name}"}


def rename_phase(db: Session, pr: models.Project, log: bool = True) -> dict | None:
    """Benennt den vorhandenen Ordner um, wenn das Phasenwort nicht mehr zum Status passt.
    Liefert None, wenn nichts zu tun war."""
    cur = current_path(pr)
    if not cur:
        return None
    old_phase = phase_of_folder(cur)
    new_phase = phase_for_status(pr.status)
    if old_phase is None or old_phase == new_phase:
        return None
    p = Path(cur)
    new_name = re.sub(r"^(\S+\s+)(Anfrage|Auftrag)\b", lambda m: m.group(1) + new_phase, p.name, count=1)
    target = p.with_name(new_name)
    try:
        if not p.is_dir():
            # Ordner gibt es (noch) nicht oder Laufwerk nicht erreichbar: nur den gespeicherten Pfad anpassen
            pr.folder_path = str(target)
            return {"ok": False, "path": str(target), "message": f"Ordner nicht erreichbar, Pfad in der App auf „{new_phase}“ gesetzt."}
        if target.exists():
            return {"ok": False, "path": cur, "message": f"Zielordner existiert bereits: {target.name}"}
        p.rename(target)
    except OSError as e:
        return {"ok": False, "path": cur, "message": f"Ordner konnte nicht umbenannt werden: {e}"}
    pr.folder_path = str(target)
    if log:
        common.log(db, "Projektordner umbenannt", project_id=pr.id, field="ordner", old=p.name, new=target.name)
    return {"ok": True, "path": str(target), "message": f"Ordner umbenannt: {target.name}"}


def sync_folder(db: Session, pr: models.Project) -> dict:
    """Manueller Abgleich: Ordner auf <Nr> <Phase> <Name> bringen oder anlegen."""
    cur = current_path(pr)
    target = expected_folder_path(db, pr)
    if not target:
        return {"ok": False, "path": cur, "message": "Basispfad fehlt oder Projektnummer hat nicht das Format JJ-NNN."}
    if not cur:
        found = find_folder(db, pr.project_number)
        if found:
            pr.folder_path = found
            cur = found
        else:
            r = create_folder(db, pr)
            if r["ok"]:
                pr.folder_path = r["path"]
                common.log(db, "Projektordner angelegt", project_id=pr.id, field="ordner", new=Path(r["path"]).name)
            return r
    if Path(cur).name == Path(target).name:
        return {"ok": True, "path": cur, "message": "Ordnername passt bereits."}
    p = Path(cur)
    try:
        if not p.is_dir():
            return {"ok": False, "path": cur, "message": f"Ordner nicht gefunden oder Laufwerk nicht erreichbar: {cur}"}
        new = p.with_name(Path(target).name)
        if new.exists():
            return {"ok": False, "path": cur, "message": f"Zielordner existiert bereits: {new.name}"}
        p.rename(new)
    except OSError as e:
        return {"ok": False, "path": cur, "message": f"Ordner konnte nicht umbenannt werden: {e}"}
    common.log(db, "Projektordner umbenannt", project_id=pr.id, field="ordner", old=p.name, new=new.name)
    pr.folder_path = str(new)
    return {"ok": True, "path": str(new), "message": f"Ordner umbenannt: {new.name}"}


def can_open_folders() -> bool:
    return platform.system() == "Windows"


def open_in_explorer(path: str) -> bool:
    if can_open_folders():
        os.startfile(path)  # type: ignore[attr-defined]
        return True
    return False
