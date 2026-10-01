"""Kalender, Zeitplan, Suche – reine Leseansichten."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from .. import models, scheduling
from ..schemas import CalendarDay, HolidayOut, ScheduleOut, ScheduleProject, ScheduleTask, SearchOut
from . import common
from .dashboard import _all_tasks


def calendar(db: Session, start: date, end: date, mine: bool = False, assignee_id: int | None = None,
             include_done: bool = False) -> list[CalendarDay]:
    p = common.params(db)
    me = common.my_user(db)
    hol = {h.date: h.name for h in db.scalars(select(models.Holiday)).all()}
    by_day: dict[date, list] = {}
    for t in _all_tasks(db):
        if mine and me and t.assignee_id != me.id:
            continue
        if assignee_id and t.assignee_id != assignee_id:
            continue
        if not t.due_date or not (start <= t.due_date <= end):
            continue
        o = common.task_out(t, p)
        if not include_done and not o.is_open:
            continue
        by_day.setdefault(t.due_date, []).append(o)
    days = []
    d = start
    while d <= end:
        tasks = sorted(by_day.get(d, []), key=lambda o: scheduling.task_sort_key(o.due_date, o.due_state, o.priority))
        days.append(CalendarDay(date=d, kw=scheduling.iso_week(d)[1], is_workday=scheduling.is_workday(d, p.holidays),
                                holiday=hol.get(d), tasks=tasks))
        d += timedelta(days=1)
    return days


def schedule(db: Session, start: date | None = None, end: date | None = None, category: str | None = None,
             project_id: int | None = None, include_done: bool = False) -> ScheduleOut:
    p = common.params(db)
    start = start or scheduling.week_start(p.today) - timedelta(days=7)
    end = end or start + timedelta(days=7 * 10 - 1)
    projects = []
    for pr in common.load_projects(db):
        if project_id and pr.id != project_id:
            continue
        if not project_id and not scheduling.project_is_active(pr.status):
            continue
        if category and pr.category not in category.split(","):
            continue
        a = scheduling.assess_project(pr, pr.tasks, p)
        rows = []
        for t in sorted(pr.tasks, key=lambda t: (t.sort_order, t.id)):
            if not include_done and not scheduling.task_is_open(t.status) and not project_id:
                continue
            if not t.due_date and not t.start_date:
                continue
            t_end = t.due_date or t.start_date
            t_start = t.start_date or scheduling.add_workdays(t_end, -2, p.holidays)
            if t_start > t_end:
                t_start = t_end
            state, _ = scheduling.due_state(t.status, t.due_date, p)
            rows.append(ScheduleTask(id=t.id, title=t.title, status=t.status, due_state=state, start=t_start, end=t_end,
                                     assignee_code=t.assignee.code if t.assignee else None,
                                     predecessor_open=bool(t.predecessor_id) and common._pred_open(t)))
        if not rows and not project_id:
            continue
        projects.append(ScheduleProject(id=pr.id, project_number=pr.project_number, name=pr.name, signal=a.signal,
                                        deadline=a.deadline, progress=a.progress, tasks=rows))
    projects.sort(key=lambda sp: (sp.deadline or date.max, sp.project_number))
    hol = [HolidayOut.model_validate(h) for h in db.scalars(select(models.Holiday).where(models.Holiday.date.between(start, end))).all()]
    return ScheduleOut(start=start, end=end, today=p.today, projects=projects, holidays=hol)


def search(db: Session, q: str, limit: int = 8) -> SearchOut:
    q = q.strip()
    if not q:
        return SearchOut(projects=[], tasks=[], notes=[])
    p = common.params(db)
    like = f"%{q}%"
    prs = db.scalars(select(models.Project).options(selectinload(models.Project.tasks)).where(or_(
        models.Project.project_number.ilike(like), models.Project.name.ilike(like), models.Project.client.ilike(like),
        models.Project.remarks.ilike(like))).limit(limit)).unique().all()
    tasks = db.scalars(select(models.Task).options(selectinload(models.Task.project).selectinload(models.Project.tasks))
                       .join(models.Project).where(or_(models.Task.title.ilike(like), models.Task.description.ilike(like),
                                                       models.Project.project_number.ilike(like)))
                       .order_by(models.Task.due_date.is_(None), models.Task.due_date).limit(limit * 2)).unique().all()
    notes = db.scalars(select(models.Note).where(models.Note.content.ilike(like)).order_by(models.Note.created_at.desc()).limit(limit)).all()
    # Bearbeiterkürzel
    users = db.scalars(select(models.User).where(models.User.code.ilike(like))).all()
    if users:
        ids = [u.id for u in users]
        prs = list(prs) + [pr for pr in common.load_projects(db) if pr.assignee_id in ids and pr not in prs][:limit]
    return SearchOut(projects=[common.project_out(pr, p) for pr in prs],
                     tasks=[common.task_out(t, p) for t in tasks],
                     notes=[common.note_out(n) for n in notes])
