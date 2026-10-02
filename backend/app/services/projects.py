from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, scheduling
from ..enums import ProjectStatus, TaskStatus
from ..schemas import ProjectCreate, ProjectDetail, ProjectOut, ProjectUpdate
from . import common, folders
from .tasks import complete_task_obj, create_task_obj


def _get(db: Session, project_id: int) -> models.Project:
    pr = db.scalar(select(models.Project).options(selectinload(models.Project.tasks)).where(models.Project.id == project_id))
    if pr is None:
        raise HTTPException(404, f"Projekt {project_id} gibt es nicht.")
    return pr


def list_projects(db: Session, status: str | None = None, active: bool | None = None, q: str = "",
                  assignee_id: int | None = None, signal: str | None = None, category: str | None = None) -> list[ProjectOut]:
    p = common.params(db)
    out = []
    for pr in common.load_projects(db):
        if status and pr.status not in status.split(","):
            continue
        if assignee_id and pr.assignee_id != assignee_id:
            continue
        if category and pr.category not in category.split(","):
            continue
        o = common.project_out(pr, p)
        if active is not None and o.is_active != active:
            continue
        if signal and o.signal not in signal.split(","):
            continue
        if q:
            hay = " ".join([pr.project_number, pr.name, pr.client or "", o.assignee_code or "", pr.participants or "", pr.remarks or ""]).lower()
            if q.lower() not in hay:
                continue
        out.append(o)
    out.sort(key=lambda o: o.project_number, reverse=True)
    out.sort(key=lambda o: 0 if o.is_active else 1)
    return out


def get_project(db: Session, project_id: int, folder_note: str | None = None) -> ProjectDetail:
    pr = _get(db, project_id)
    cur = folders.current_path(pr)
    if not cur or (not Path(cur).is_dir() and folders.base_reachable_dir(db, cur)):
        # Kein Pfad gemerkt oder der gemerkte Ordner wurde auf dem NAS umbenannt: nur lesend neu suchen
        found = folders.find_folder(db, pr.project_number)
        if found and found != cur:
            pr.folder_path = found
            common.log(db, "Projektordner übernommen", project_id=pr.id, field="ordner", new=Path(found).name)
            db.commit()
            folder_note = folder_note or f"Vorhandener Ordner übernommen: {Path(found).name}"
    p = common.params(db)
    base = common.project_out(pr, p)
    tasks = sorted(pr.tasks, key=lambda t: (t.sort_order, t.id))
    notes = db.scalars(select(models.Note).where(models.Note.project_id == pr.id).order_by(models.Note.created_at.desc(), models.Note.id.desc())).all()
    return ProjectDetail(**base.model_dump(), tasks=[common.task_out(t, p) for t in tasks], notes=[common.note_out(n) for n in notes],
                         folder_note=folder_note or folders.folder_hint(db, pr))


def _check_number(db: Session, number: str, exclude_id: int | None = None) -> None:
    existing = db.scalar(select(models.Project).where(models.Project.project_number == number))
    if existing is not None and existing.id != exclude_id:
        raise HTTPException(409, f"Die Projektnummer {number} ist bereits vergeben ({existing.name}).")


def _check_user(db: Session, user_id: int | None) -> None:
    if user_id is not None and db.get(models.User, user_id) is None:
        raise HTTPException(422, "Der gewählte Bearbeiter existiert nicht.")


def create_project(db: Session, data: ProjectCreate) -> ProjectDetail:
    _check_number(db, data.project_number)
    _check_user(db, data.assignee_id)
    pr = models.Project(**data.model_dump(exclude={"template_id", "compute_due_dates"}))
    if pr.assignee_id is None:
        me = common.my_user(db)
        pr.assignee_id = me.id if me else None
    folder = (pr.folder_path or "").strip()
    if not folder:
        folder = folders.find_folder(db, pr.project_number) or ""
    pr.folder_path = folder
    db.add(pr)
    db.flush()
    common.log(db, "Projekt angelegt", project_id=pr.id, field="status", new=pr.status)
    note = None
    if folder and folder != (data.folder_path or "").strip():
        note = f"Vorhandener Ordner übernommen: {Path(folder).name}"
        common.log(db, "Projektordner übernommen", project_id=pr.id, field="ordner", new=Path(folder).name)
    if data.template_id:
        apply_template(db, pr, data.template_id, None, data.compute_due_dates)
    db.commit()
    return get_project(db, pr.id, note)


def update_project(db: Session, project_id: int, data: ProjectUpdate) -> ProjectDetail:
    pr = _get(db, project_id)
    changes = data.model_dump(exclude_unset=True, exclude={"clear"})
    if "project_number" in changes:
        _check_number(db, changes["project_number"], pr.id)
    if "assignee_id" in changes:
        _check_user(db, changes["assignee_id"])
    tracked = {"status", "priority", "assignee_id", "target_deadline", "order_date", "offered_weeks", "project_number", "name", "client", "category"}
    for k, v in changes.items():
        old = getattr(pr, k)
        if old == v:
            continue
        setattr(pr, k, v)
        if k in tracked:
            common.log(db, "Projekt geändert", project_id=pr.id, field=k, old=_label(db, k, old), new=_label(db, k, v))
    for k in data.clear:
        if hasattr(pr, k) and getattr(pr, k) is not None:
            common.log(db, "Projekt geändert", project_id=pr.id, field=k, old=getattr(pr, k), new="")
            setattr(pr, k, None)
    # Auftragsdatum eingetragen, Status noch Anfrage/Angebot -> Beauftragt
    if changes.get("order_date") and pr.status in (ProjectStatus.anfrage, ProjectStatus.angebot) and "status" not in changes:
        common.log(db, "Projekt geändert", project_id=pr.id, field="status", old=pr.status, new=ProjectStatus.beauftragt)
        pr.status = ProjectStatus.beauftragt
    if "status" in changes and changes["status"] == ProjectStatus.abgeschlossen and pr.completed_at is None:
        pr.completed_at = date.today()
    common.touch(pr)
    db.commit()
    return get_project(db, pr.id)


def _label(db: Session, field: str, v):
    if field == "assignee_id" and v is not None:
        u = db.get(models.User, v)
        return u.code if u else v
    return v


def delete_project(db: Session, project_id: int) -> None:
    pr = _get(db, project_id)
    common.log(db, "Projekt gelöscht", project_id=None, details=f"{pr.project_number} {pr.name}")
    db.delete(pr)
    db.commit()


def complete_project(db: Session, project_id: int, open_tasks: str) -> ProjectDetail:
    pr = _get(db, project_id)
    for t in pr.tasks:
        if scheduling.task_is_open(t.status):
            if open_tasks == "erledigt":
                complete_task_obj(db, t)
            elif open_tasks == "entfaellt":
                common.log(db, "Aufgabe entfällt", project_id=pr.id, task_id=t.id, field="status", old=t.status, new=TaskStatus.entfaellt)
                t.status = TaskStatus.entfaellt
    common.log(db, "Projekt abgeschlossen", project_id=pr.id, field="status", old=pr.status, new=ProjectStatus.abgeschlossen)
    pr.status = ProjectStatus.abgeschlossen
    pr.completed_at = date.today()
    common.touch(pr)
    db.commit()
    return get_project(db, pr.id)


# ---------------------------------------------------------------- Vorlagen --
def apply_template(db: Session, pr: models.Project, template_id: int, deadline: date | None, compute: bool) -> int:
    tpl = db.get(models.ProjectTemplate, template_id)
    if tpl is None:
        raise HTTPException(404, "Vorlage nicht gefunden.")
    p = common.params(db)
    if deadline is None:
        deadline = scheduling.effective_deadline(pr.target_deadline, pr.order_date, pr.offered_weeks)
    offsets = [tt.offset_workdays for tt in tpl.tasks]
    dues = scheduling.template_due_dates(deadline if compute else None, offsets, p.holidays, p.today)
    base_order = max([t.sort_order for t in pr.tasks], default=0)
    prev_id: int | None = None
    n = 0
    for i, (tt, due) in enumerate(zip(tpl.tasks, dues), start=1):
        assignee_id = pr.assignee_id
        if tt.assignee_role and tt.assignee_role.upper() != "PL":
            u = db.scalar(select(models.User).where(models.User.code == tt.assignee_role.upper()))
            if u:
                assignee_id = u.id
        weight = tt.weight if tt.weight is not None else (tt.task_type.default_weight if tt.task_type else 1.0)
        t = create_task_obj(db, project=pr, title=tt.title, task_type_id=tt.task_type_id, assignee_id=assignee_id,
                            due_date=due, weight=weight, sort_order=base_order + i,
                            predecessor_id=prev_id if tt.depends_on_previous else None, log_each=False)
        prev_id = t.id
        n += 1
    common.log(db, "Vorlage angewendet", project_id=pr.id, field="vorlage", new=tpl.name, details=f"{n} Aufgaben")
    common.touch(pr)
    return n


def apply_template_endpoint(db: Session, project_id: int, template_id: int, deadline: date | None, compute: bool) -> ProjectDetail:
    pr = _get(db, project_id)
    apply_template(db, pr, template_id, deadline, compute)
    db.commit()
    return get_project(db, pr.id)


# ------------------------------------------------------------ Projektordner --
def folder_lookup(db: Session, project_number: str, status: str, name: str) -> dict:
    """Vorschau fürs Projektformular: erwarteter Ordner und ob er schon da ist. Nur lesend."""
    nr = project_number.strip()
    pr = models.Project(project_number=nr, status=status or "anfrage", name=name or "")
    expected = folders.expected_folder_path(db, pr) if nr else None
    found = folders.find_folder(db, nr) if nr else None
    return {"expected": expected, "found": found}


def can_open_folders() -> bool:
    return folders.can_open_folders()


def open_folder(db: Session, project_id: int) -> dict:
    pr = _get(db, project_id)
    path = folders.current_path(pr)
    if not path or not Path(path).is_dir():
        found = folders.find_folder(db, pr.project_number)
        if found:
            pr.folder_path = found
            db.commit()
            path = found
    if not path:
        raise HTTPException(404, f"Für {pr.project_number} ist kein Projektordner hinterlegt und im Basispfad wurde keiner gefunden. Pfad im Projekt eintragen (Bearbeiten).")
    if not Path(path).is_dir():
        raise HTTPException(404, f"Der Ordner existiert nicht oder das Laufwerk ist nicht erreichbar: {path}")
    if folders.open_in_explorer(path):
        return {"opened": True, "path": path}
    return {"opened": False, "path": path, "message": "Ordner öffnen geht nur unter Windows. Pfad zum Kopieren:"}
