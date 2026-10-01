from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, scheduling
from ..enums import DueState, ProjectStatus, Signal, TaskStatus
from ..schemas import AttentionItem, DashboardCounts, DashboardOut, NotificationOut
from . import common


def _all_tasks(db: Session) -> list[models.Task]:
    stmt = select(models.Task).options(selectinload(models.Task.project).selectinload(models.Project.tasks))
    return list(db.scalars(stmt).unique().all())


def build(db: Session) -> DashboardOut:
    p = common.params(db)
    s = common.settings_out(db)
    me = common.my_user(db)
    projects = [common.project_out(pr, p) for pr in common.load_projects(db)]
    tasks = [common.task_out(t, p) for t in _all_tasks(db)]
    open_tasks = [t for t in tasks if t.is_open]
    ws = scheduling.week_start(p.today)

    def in_week(t, offset_weeks: int) -> bool:
        return bool(t.due_date) and ws + timedelta(days=7 * offset_weeks) <= t.due_date <= ws + timedelta(days=7 * offset_weeks + 6)

    today = [t for t in open_tasks if t.due_state == DueState.heute]
    overdue = [t for t in open_tasks if t.due_state == DueState.ueberfaellig]
    soon = [t for t in open_tasks if t.due_state == DueState.demnaechst]
    this_week = [t for t in open_tasks if in_week(t, 0)]
    next_week = [t for t in open_tasks if in_week(t, 1)]
    waiting = [t for t in open_tasks if t.status == TaskStatus.wartet]
    upcoming = [t for t in open_tasks if t.due_date and p.today < t.due_date <= p.today + timedelta(days=7)]
    active = [o for o in projects if o.is_active]
    critical = [o for o in active if o.signal == Signal.rot]
    attention_projects = [o for o in active if o.signal in (Signal.rot, Signal.gelb) or o.warnings]
    attention_projects.sort(key=lambda o: (0 if o.signal == Signal.rot else 1 if o.signal == Signal.gelb else 2, o.deadline or scheduling.date.max))
    waiting_projects = [o for o in active if o.status == ProjectStatus.wartet_kunde or o.waiting_count > 0]

    key = lambda t: scheduling.task_sort_key(t.due_date, t.due_state, t.priority)  # noqa: E731
    for lst in (today, overdue, soon, upcoming, waiting):
        lst.sort(key=key)
    waiting.sort(key=lambda t: (t.waiting_since or scheduling.date.max, t.id))

    counts = DashboardCounts(
        today=len(today), overdue=len(overdue), this_week=len(this_week), next_week=len(next_week), soon=len(soon),
        active_projects=len(active), critical_projects=len(critical), waiting_tasks=len(waiting),
        waiting_projects=len(waiting_projects),
        inquiries=sum(1 for o in projects if o.status == ProjectStatus.anfrage),
        offers=sum(1 for o in projects if o.status == ProjectStatus.angebot),
        my_open=sum(1 for t in open_tasks if me and t.assignee_id == me.id),
        others_open=sum(1 for t in open_tasks if not me or t.assignee_id != me.id),
        no_due=sum(1 for t in open_tasks if t.due_state == DueState.ohne_frist),
    )

    attention: list[AttentionItem] = []
    for t in overdue:
        attention.append(AttentionItem(kind="task", level="rot", title=t.title, subtitle=f"{t.project_number} · {t.project_name}",
                                       reason=f"{t.days_overdue} Tag{'e' if t.days_overdue != 1 else ''} überfällig",
                                       task_id=t.id, project_id=t.project_id, project_number=t.project_number, due_date=t.due_date))
    for t in today:
        attention.append(AttentionItem(kind="task", level="orange", title=t.title, subtitle=f"{t.project_number} · {t.project_name}",
                                       reason="heute fällig", task_id=t.id, project_id=t.project_id, project_number=t.project_number, due_date=t.due_date))
    for o in critical:
        attention.append(AttentionItem(kind="project", level="rot", title=f"{o.project_number} · {o.name}", subtitle=o.client or "",
                                       reason=", ".join(o.reasons), project_id=o.id, project_number=o.project_number, due_date=o.deadline))
    for t in soon:
        attention.append(AttentionItem(kind="task", level="gelb", title=t.title, subtitle=f"{t.project_number} · {t.project_name}",
                                       reason=f"fällig {t.due_date.strftime('%d.%m.')}", task_id=t.id, project_id=t.project_id,
                                       project_number=t.project_number, due_date=t.due_date))

    activity = db.scalars(select(models.ActivityLog).order_by(models.ActivityLog.created_at.desc(), models.ActivityLog.id.desc()).limit(12)).all()
    active_sorted = sorted(active, key=lambda o: (o.deadline or scheduling.date.max, o.project_number))

    return DashboardOut(
        today=p.today, greeting_name=(me.name.split(" ")[0] if me and me.name else (me.code if me else "")),
        kw=scheduling.iso_week(p.today)[1], counts=counts, attention=attention,
        today_tasks=today, overdue_tasks=overdue, upcoming=upcoming[:15], waiting=waiting,
        projects_attention=attention_projects[:12], active_projects=active_sorted,
        recent_activity=[common.activity_out(a) for a in activity], widgets=s.dashboard_widgets,
    )


def notifications(db: Session) -> list[NotificationOut]:
    p = common.params(db)
    out: list[NotificationOut] = []
    for t in _all_tasks(db):
        o = common.task_out(t, p)
        if o.due_state == DueState.ueberfaellig:
            out.append(NotificationOut(level="rot", text=f"„{o.title}“ ({o.project_number}) ist seit {o.days_overdue} Tag{'en' if o.days_overdue != 1 else ''} überfällig.", task_id=o.id, project_id=o.project_id))
        elif o.due_state == DueState.heute:
            out.append(NotificationOut(level="orange", text=f"„{o.title}“ ({o.project_number}) ist heute fällig.", task_id=o.id, project_id=o.project_id))
        if o.is_open and o.reminder_date and o.reminder_date <= p.today:
            out.append(NotificationOut(level="blau", text=f"Erinnerung: „{o.title}“ ({o.project_number}) wartet auf {o.waiting_for or 'Rückmeldung'}{' von ' + o.waiting_on if o.waiting_on else ''}.", task_id=o.id, project_id=o.project_id))
    for pr in common.load_projects(db):
        o = common.project_out(pr, p)
        if not o.is_active or o.deadline is None:
            continue
        if o.deadline < p.today:
            out.append(NotificationOut(level="rot", text=f"Projekt {o.project_number} hat seine Frist seit {(p.today - o.deadline).days} Tagen überschritten.", project_id=o.id))
        elif o.remaining_workdays is not None and o.remaining_workdays <= p.warn_project_workdays:
            out.append(NotificationOut(level="gelb", text=f"Projekt {o.project_number} erreicht seine Frist in {o.remaining_workdays} Arbeitstag{'en' if o.remaining_workdays != 1 else ''} ({o.deadline.strftime('%d.%m.')}).", project_id=o.id))
    order = {"rot": 0, "orange": 1, "gelb": 2, "blau": 3}
    out.sort(key=lambda n: order.get(n.level, 9))
    return out
