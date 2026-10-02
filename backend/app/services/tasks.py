from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, scheduling
from ..enums import DueState, TaskStatus
from ..schemas import TaskCreate, TaskOut, TaskUpdate
from . import common


def _get(db: Session, task_id: int) -> models.Task:
    t = db.scalar(select(models.Task).options(selectinload(models.Task.project).selectinload(models.Project.tasks)).where(models.Task.id == task_id))
    if t is None:
        raise HTTPException(404, f"Aufgabe {task_id} gibt es nicht.")
    return t


def create_task_obj(db: Session, project: models.Project, title: str, task_type_id: int | None = None,
                    assignee_id: int | None = None, status: TaskStatus = TaskStatus.nicht_begonnen,
                    priority=None, start_date: date | None = None, due_date: date | None = None,
                    weight: float | None = None, progress: int = 0, predecessor_id: int | None = None,
                    sort_order: int | None = None, description: str = "", waiting_for: str = "",
                    waiting_on: str = "", waiting_since: date | None = None, reminder_date: date | None = None,
                    log_each: bool = True) -> models.Task:
    if weight is None:
        tt = db.get(models.TaskType, task_type_id) if task_type_id else None
        weight = tt.default_weight if tt else 1.0
    if sort_order is None:
        sort_order = max([t.sort_order for t in project.tasks], default=0) + 1
    t = models.Task(
        project_id=project.id, title=title.strip(), task_type_id=task_type_id, assignee_id=assignee_id,
        status=status, priority=priority or "normal", start_date=start_date, due_date=due_date,
        weight=float(weight), progress=100 if status == TaskStatus.erledigt else int(progress or 0),
        predecessor_id=predecessor_id, sort_order=sort_order, description=description or "",
        waiting_for=waiting_for or "", waiting_on=waiting_on or "", waiting_since=waiting_since,
        reminder_date=reminder_date, completed_at=date.today() if status == TaskStatus.erledigt else None,
        round_id=common.current_round_id(project),
    )
    db.add(t)
    db.flush()
    project.tasks.append(t)
    if log_each:
        common.log(db, "Aufgabe angelegt", project_id=project.id, task_id=t.id, field="aufgabe", new=t.title,
                   details=f"Frist {due_date.strftime('%d.%m.%Y')}" if due_date else "")
    common.touch(project)
    return t


def _load_task_out(db: Session, task_id: int) -> TaskOut:
    t = _get(db, task_id)
    return common.task_out(t, common.params(db))


def list_tasks(db: Session, assignee_id: int | None = None, mine: bool = False, project_id: int | None = None,
               status: str | None = None, open_only: bool = True, bucket: str | None = None,
               priority: str | None = None, task_type_id: int | None = None, q: str = "",
               category: str | None = None, limit: int | None = None) -> list[TaskOut]:
    p = common.params(db)
    stmt = select(models.Task).options(selectinload(models.Task.project).selectinload(models.Project.tasks))
    if project_id:
        stmt = stmt.where(models.Task.project_id == project_id)
    if mine:
        me = common.my_user(db)
        if me:
            stmt = stmt.where(models.Task.assignee_id == me.id)
    elif assignee_id:
        stmt = stmt.where(models.Task.assignee_id == assignee_id)
    if status:
        stmt = stmt.where(models.Task.status.in_(status.split(",")))
    elif open_only:
        stmt = stmt.where(models.Task.status.in_([s.value for s in scheduling.OPEN_TASK_STATUSES]))
    if priority:
        stmt = stmt.where(models.Task.priority.in_(priority.split(",")))
    if task_type_id:
        stmt = stmt.where(models.Task.task_type_id == task_type_id)
    rows = db.scalars(stmt).unique().all()
    out = []
    for t in rows:
        if category and t.project and t.project.category not in category.split(","):
            continue
        if not common.task_in_current_round(t):
            continue
        o = common.task_out(t, p)
        if bucket:
            if bucket == "next_week":
                ws = scheduling.week_start(p.today)
                if not (o.due_date and ws + scheduling.timedelta(days=7) <= o.due_date <= ws + scheduling.timedelta(days=13)):
                    continue
            elif bucket == "this_week":
                ws = scheduling.week_start(p.today)
                if not (o.due_date and ws <= o.due_date <= ws + scheduling.timedelta(days=6) and o.is_open):
                    continue
            elif o.due_state.value != bucket:
                continue
        if q:
            hay = " ".join([o.title, o.project_number, o.project_name, o.description, o.assignee_code or "", o.task_type_name or ""]).lower()
            if q.lower() not in hay:
                continue
        out.append(o)
    out.sort(key=lambda o: scheduling.task_sort_key(o.due_date, o.due_state, o.priority))
    return out[:limit] if limit else out


def get_task(db: Session, task_id: int) -> TaskOut:
    return _load_task_out(db, task_id)


def create_task(db: Session, data: TaskCreate) -> TaskOut:
    pr = db.scalar(select(models.Project).options(selectinload(models.Project.tasks)).where(models.Project.id == data.project_id))
    if pr is None:
        raise HTTPException(422, "Das gewählte Projekt existiert nicht.")
    if data.assignee_id is not None and db.get(models.User, data.assignee_id) is None:
        raise HTTPException(422, "Der gewählte Bearbeiter existiert nicht.")
    if data.predecessor_id is not None:
        pred = db.get(models.Task, data.predecessor_id)
        if pred is None or pred.project_id != pr.id:
            raise HTTPException(422, "Die Vorgängeraufgabe gehört nicht zu diesem Projekt.")
    if data.start_date and data.due_date and data.start_date > data.due_date:
        raise HTTPException(422, "Das Startdatum liegt nach der Frist.")
    assignee = data.assignee_id
    if assignee is None:
        me = common.my_user(db)
        assignee = me.id if me else pr.assignee_id
    t = create_task_obj(db, pr, data.title, data.task_type_id, assignee, data.status, data.priority, data.start_date,
                        data.due_date, data.weight, data.progress, data.predecessor_id, None, data.description,
                        data.waiting_for, data.waiting_on, data.waiting_since, data.reminder_date)
    if data.note.strip():
        from .notes import add_note_obj
        add_note_obj(db, pr.id, t.id, data.note.strip())
    db.commit()
    return _load_task_out(db, t.id)


TRACKED = {"status": "Status", "due_date": "Frist", "assignee_id": "Bearbeiter", "priority": "Priorität",
           "progress": "Fortschritt", "title": "Aufgabe", "start_date": "Start", "waiting_for": "Wartet auf"}


def update_task(db: Session, task_id: int, data: TaskUpdate) -> TaskOut:
    t = _get(db, task_id)
    changes = data.model_dump(exclude_unset=True, exclude={"clear"})
    if "assignee_id" in changes and changes["assignee_id"] is not None and db.get(models.User, changes["assignee_id"]) is None:
        raise HTTPException(422, "Der gewählte Bearbeiter existiert nicht.")
    if "predecessor_id" in changes and changes["predecessor_id"] is not None:
        pred = db.get(models.Task, changes["predecessor_id"])
        if pred is None or pred.project_id != t.project_id or pred.id == t.id:
            raise HTTPException(422, "Die Vorgängeraufgabe gehört nicht zu diesem Projekt.")
    new_start = changes.get("start_date", t.start_date)
    new_due = changes.get("due_date", t.due_date)
    if new_start and new_due and new_start > new_due and "start_date" not in data.clear and "due_date" not in data.clear:
        raise HTTPException(422, "Das Startdatum liegt nach der Frist.")

    for k, v in changes.items():
        old = getattr(t, k)
        if old == v:
            continue
        setattr(t, k, v)
        if k in TRACKED:
            common.log(db, "Aufgabe geändert", project_id=t.project_id, task_id=t.id, field=k, old=_label(db, k, old), new=_label(db, k, v))
    for k in data.clear:
        if hasattr(t, k) and getattr(t, k) is not None:
            if k in TRACKED:
                common.log(db, "Aufgabe geändert", project_id=t.project_id, task_id=t.id, field=k, old=getattr(t, k), new="")
            setattr(t, k, None)
    _apply_status_side_effects(t)
    common.touch(t.project)
    db.commit()
    return _load_task_out(db, t.id)


def _label(db: Session, field: str, v):
    if field == "assignee_id" and v is not None:
        u = db.get(models.User, v)
        return u.code if u else v
    return v


def _apply_status_side_effects(t: models.Task) -> None:
    if t.status == TaskStatus.erledigt:
        t.progress = 100
        if t.completed_at is None:
            t.completed_at = date.today()
    elif t.completed_at is not None and t.status != TaskStatus.erledigt:
        t.completed_at = None
    if t.status == TaskStatus.wartet and t.waiting_since is None:
        t.waiting_since = date.today()


def complete_task_obj(db: Session, t: models.Task) -> None:
    old = t.status
    t.status = TaskStatus.erledigt
    t.progress = 100
    t.completed_at = date.today()
    common.log(db, "Aufgabe erledigt", project_id=t.project_id, task_id=t.id, field="status", old=old, new=TaskStatus.erledigt)


def complete_task(db: Session, task_id: int) -> TaskOut:
    t = _get(db, task_id)
    if t.status == TaskStatus.erledigt:
        return common.task_out(t, common.params(db))
    complete_task_obj(db, t)
    common.touch(t.project)
    db.commit()
    return _load_task_out(db, t.id)


def reopen_task(db: Session, task_id: int) -> TaskOut:
    t = _get(db, task_id)
    old = t.status
    t.status = TaskStatus.in_bearbeitung
    t.completed_at = None
    if t.progress >= 100:
        t.progress = 0
    common.log(db, "Aufgabe wieder geöffnet", project_id=t.project_id, task_id=t.id, field="status", old=old, new=t.status)
    common.touch(t.project)
    db.commit()
    return _load_task_out(db, t.id)


def delete_task(db: Session, task_id: int) -> None:
    t = _get(db, task_id)
    common.log(db, "Aufgabe gelöscht", project_id=t.project_id, task_id=None, details=t.title)
    common.touch(t.project)
    db.delete(t)
    db.commit()


def reorder_tasks(db: Session, project_id: int, task_ids: list[int]) -> list[TaskOut]:
    pr = db.scalar(select(models.Project).options(selectinload(models.Project.tasks)).where(models.Project.id == project_id))
    if pr is None:
        raise HTTPException(404, "Projekt nicht gefunden.")
    pos = {tid: i + 1 for i, tid in enumerate(task_ids)}
    for t in pr.tasks:
        if t.id in pos:
            t.sort_order = pos[t.id]
    db.commit()
    p = common.params(db)
    return [common.task_out(t, p) for t in sorted(pr.tasks, key=lambda t: (t.sort_order, t.id))]


def shift_due(db: Session, task_id: int, workdays: int) -> TaskOut:
    """Frist um n Arbeitstage verschieben (von der Frist aus, sonst von heute)."""
    t = _get(db, task_id)
    p = common.params(db)
    base = t.due_date or p.today
    new = scheduling.add_workdays(base, workdays, p.holidays)
    common.log(db, "Aufgabe geändert", project_id=t.project_id, task_id=t.id, field="due_date", old=t.due_date, new=new)
    t.due_date = new
    common.touch(t.project)
    db.commit()
    return _load_task_out(db, t.id)
