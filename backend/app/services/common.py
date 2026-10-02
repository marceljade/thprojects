"""Gemeinsame Bausteine: Einstellungen, Parameter, Protokoll, Serialisierung."""
from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, scheduling
from ..enums import TaskStatus
from ..schemas import ActivityOut, NoteOut, ProjectOut, RoundOut, TaskOut, SettingsOut

DEFAULT_WIDGETS = {"attention": True, "today": True, "overdue": True, "upcoming": True,
                   "waiting": True, "projects": True, "active_projects": True, "activity": True}


# ---------------------------------------------------------------- Settings --
def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(models.Setting, key)
    return row.value if row is not None else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(models.Setting, key)
    if row is None:
        db.add(models.Setting(key=key, value=value))
    else:
        row.value = value


def settings_out(db: Session) -> SettingsOut:
    my_id = get_setting(db, "my_user_id", "")
    user = db.get(models.User, int(my_id)) if my_id.isdigit() else None
    try:
        widgets = {**DEFAULT_WIDGETS, **json.loads(get_setting(db, "dashboard_widgets", "{}"))}
    except json.JSONDecodeError:
        widgets = dict(DEFAULT_WIDGETS)
    return SettingsOut(
        my_user_id=user.id if user else None,
        my_user_code=user.code if user else None,
        base_path=get_setting(db, "base_path", ""),
        warn_workdays=int(get_setting(db, "warn_workdays", "3") or 3),
        warn_project_workdays=int(get_setting(db, "warn_project_workdays", "5") or 5),
        auto_backup=get_setting(db, "auto_backup", "1") == "1",
        dashboard_widgets=widgets,
    )


def my_user(db: Session) -> models.User | None:
    my_id = get_setting(db, "my_user_id", "")
    return db.get(models.User, int(my_id)) if my_id.isdigit() else None


def holidays(db: Session) -> set[date]:
    return {h.date for h in db.scalars(select(models.Holiday)).all()}


def params(db: Session, today: date | None = None) -> scheduling.Params:
    s = settings_out(db)
    return scheduling.Params(today=today or date.today(), holidays=holidays(db),
                             warn_workdays=s.warn_workdays, warn_project_workdays=s.warn_project_workdays)


# ---------------------------------------------------------------- Protokoll --
def log(db: Session, action: str, project_id: int | None = None, task_id: int | None = None,
        field: str = "", old: object = "", new: object = "", details: str = "") -> None:
    me = my_user(db)
    db.add(models.ActivityLog(
        project_id=project_id, task_id=task_id, user_id=me.id if me else None,
        action=action, field=field, old_value=fmt(old), new_value=fmt(new), details=details,
    ))


def fmt(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, (date, datetime)):
        return v.strftime("%d.%m.%Y")
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


def touch(project: models.Project) -> None:
    project.updated_at = datetime.now()


# ------------------------------------------------------------------ Runden --
def current_round(pr: models.Project) -> models.ProjectRound | None:
    """Aktuelle Runde = höchste Nummer. None nur, bevor die Migration gelaufen ist."""
    return max(pr.rounds, key=lambda r: r.number) if pr.rounds else None


def current_round_id(pr: models.Project) -> int | None:
    r = current_round(pr)
    return r.id if r else None


def task_in_current_round(t: models.Task) -> bool:
    if not t.project or t.round_id is None:
        return True
    return t.round_id == current_round_id(t.project)


def sync_round(pr: models.Project) -> None:
    """Projektfelder sind die Quelle, die aktuelle Runde spiegelt sie."""
    r = current_round(pr)
    if r is None:
        return
    r.status = pr.status
    r.request_date = pr.request_date
    r.offer_date = pr.offer_date
    r.order_date = pr.order_date
    r.offered_weeks = pr.offered_weeks
    r.target_deadline = pr.target_deadline


def round_out(r: models.ProjectRound, pr: models.Project) -> RoundOut:
    tasks = [t for t in pr.tasks if t.round_id == r.id]
    return RoundOut(id=r.id, project_id=r.project_id, number=r.number, title=r.title, status=r.status,
                    request_date=r.request_date, offer_date=r.offer_date, order_date=r.order_date, offered_weeks=r.offered_weeks,
                    target_deadline=r.target_deadline, closed_at=r.closed_at, created_at=r.created_at,
                    task_count=sum(1 for t in tasks if TaskStatus(t.status) != TaskStatus.entfaellt),
                    open_count=sum(1 for t in tasks if scheduling.task_is_open(t.status)),
                    progress=scheduling.project_progress(tasks, r.status))


# ------------------------------------------------------------ Serialisierung --
def task_out(t: models.Task, p: scheduling.Params, pred_open: bool | None = None) -> TaskOut:
    state, overdue = scheduling.due_state(t.status, t.due_date, p)
    if pred_open is None:
        pred_open = bool(t.predecessor_id) and _pred_open(t)
    rnd = next((r for r in t.project.rounds if r.id == t.round_id), None) if t.project and t.round_id else None
    return TaskOut(
        id=t.id, project_id=t.project_id,
        project_number=t.project.project_number if t.project else "",
        project_name=t.project.name if t.project else "",
        title=t.title, task_type_id=t.task_type_id,
        task_type_name=t.task_type.name if t.task_type else None,
        description=t.description or "", assignee_id=t.assignee_id,
        assignee_code=t.assignee.code if t.assignee else None,
        status=TaskStatus(t.status), priority=t.priority, start_date=t.start_date, due_date=t.due_date,
        completed_at=t.completed_at, progress=scheduling.effective_progress(t.status, t.progress),
        weight=t.weight, predecessor_id=t.predecessor_id, predecessor_open=pred_open,
        sort_order=t.sort_order, waiting_for=t.waiting_for or "", waiting_on=t.waiting_on or "",
        waiting_since=t.waiting_since, reminder_date=t.reminder_date,
        created_at=t.created_at, updated_at=t.updated_at,
        due_state=state, days_overdue=overdue,
        kw=scheduling.iso_week(t.due_date)[1] if t.due_date else None,
        is_open=scheduling.task_is_open(t.status),
        round_id=t.round_id, round_number=rnd.number if rnd else (current_round(t.project).number if t.project and t.project.rounds else 1),
        is_current_round=task_in_current_round(t),
    )


def _pred_open(t: models.Task) -> bool:
    # Vorgänger liegt im selben Projekt, die Tasks-Liste ist geladen
    if not t.project:
        return False
    for other in t.project.tasks:
        if other.id == t.predecessor_id:
            return scheduling.task_is_open(other.status)
    return False


def project_out(pr: models.Project, p: scheduling.Params) -> ProjectOut:
    rnd = current_round(pr)
    a = scheduling.assess_project(pr, pr.tasks, p, rnd.id if rnd else None)
    return ProjectOut(
        id=pr.id, project_number=pr.project_number, name=pr.name, client=pr.client or "",
        category=pr.category, assignee_id=pr.assignee_id,
        assignee_code=pr.assignee.code if pr.assignee else None, participants=pr.participants or "",
        status=pr.status, priority=pr.priority, request_date=pr.request_date, offer_date=pr.offer_date,
        order_date=pr.order_date, offered_weeks=pr.offered_weeks, target_deadline=pr.target_deadline,
        completed_at=pr.completed_at, folder_path=pr.folder_path or "", remarks=pr.remarks or "",
        created_at=pr.created_at, updated_at=pr.updated_at,
        is_active=scheduling.project_is_active(pr.status),
        contractual_deadline=scheduling.contractual_deadline(pr.order_date, pr.offered_weeks),
        deadline=a.deadline, deadline_kw=scheduling.iso_week(a.deadline)[1] if a.deadline else None,
        remaining_workdays=a.remaining_workdays, progress=a.progress, signal=a.signal,
        reasons=a.reasons, warnings=a.warnings, task_count=a.task_count, open_count=a.open_count,
        overdue_count=a.overdue_count, waiting_count=a.waiting_count, next_task_id=a.next_task_id,
        next_task_title=a.next_task_title, next_due=a.next_due,
        expected_folder_name=_folders().expected_folder_name(pr), folder_matches=_folders().folder_matches(pr),
        round_number=rnd.number if rnd else 1, round_title=rnd.title if rnd else "Erstauftrag",
    )


def _folders():
    from . import folders
    return folders


def note_out(n: models.Note) -> NoteOut:
    return NoteOut(
        id=n.id, project_id=n.project_id, project_number=n.project.project_number if n.project else "",
        task_id=n.task_id, task_title=n.task.title if n.task else None, author_id=n.author_id,
        author_code=n.author.code if n.author else None, content=n.content, created_at=n.created_at,
    )


def activity_out(a: models.ActivityLog) -> ActivityOut:
    return ActivityOut(
        id=a.id, project_id=a.project_id, project_number=a.project.project_number if a.project else None,
        task_id=a.task_id, task_title=a.task.title if a.task else None,
        user_code=a.user.code if a.user else None, action=a.action, field=a.field,
        old_value=a.old_value, new_value=a.new_value, details=a.details, created_at=a.created_at,
    )


def load_projects(db: Session, ids: list[int] | None = None) -> list[models.Project]:
    stmt = select(models.Project).options(selectinload(models.Project.tasks), selectinload(models.Project.rounds))
    if ids is not None:
        stmt = stmt.where(models.Project.id.in_(ids))
    return list(db.scalars(stmt).unique().all())
