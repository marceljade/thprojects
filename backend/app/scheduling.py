"""Die einzige Stelle für Fristen-, Fortschritts- und Ampellogik.

Alle Funktionen sind reine Python-Funktionen ohne Datenbankzugriff, damit sie
einfach testbar sind. Die Services reichen Projekte, Aufgaben, Feiertage und
Parameter herein.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .enums import (
    ACTIVE_PROJECT_STATUSES, CLOSED_PROJECT_STATUSES, OPEN_TASK_STATUSES, DUE_STATE_RANK, PRIORITY_RANK,
    DueState, Priority, ProjectStatus, Signal, TaskStatus,
)


@dataclass
class Params:
    today: date
    holidays: set[date] = field(default_factory=set)
    warn_workdays: int = 3          # Aufgabe gilt als "Demnächst"
    warn_project_workdays: int = 5  # Projekt wird gelb


# ----------------------------------------------------------------- Kalender --
def is_workday(d: date, holidays: set[date]) -> bool:
    return d.weekday() < 5 and d not in holidays


def add_workdays(start: date, n: int, holidays: set[date]) -> date:
    """Wie Excel ARBEITSTAG: n Arbeitstage ab start (start selbst zählt nicht)."""
    d = start
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    while remaining > 0:
        d += timedelta(days=step)
        if is_workday(d, holidays):
            remaining -= 1
    return d


def workdays_between(a: date, b: date, holidays: set[date]) -> int:
    """Arbeitstage von a (exklusiv) bis b (inklusiv). Negativ, wenn b vor a liegt."""
    if b < a:
        return -workdays_between(b, a, holidays)
    n = 0
    d = a
    while d < b:
        d += timedelta(days=1)
        if is_workday(d, holidays):
            n += 1
    return n


def iso_week(d: date) -> tuple[int, int]:
    y, w, _ = d.isocalendar()
    return y, w


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ----------------------------------------------------------------- Aufgaben --
def task_is_open(status: TaskStatus) -> bool:
    return TaskStatus(status) in OPEN_TASK_STATUSES


def due_state(status: TaskStatus, due: date | None, p: Params) -> tuple[DueState, int]:
    """Liefert (Zustand, Tage überfällig). Erledigte Aufgaben sind nie überfällig."""
    if not task_is_open(status):
        return DueState.erledigt, 0
    if due is None:
        return DueState.ohne_frist, 0
    if due < p.today:
        return DueState.ueberfaellig, (p.today - due).days
    if due == p.today:
        return DueState.heute, 0
    if due <= add_workdays(p.today, p.warn_workdays, p.holidays):
        return DueState.demnaechst, 0
    if due <= p.today + timedelta(days=7):
        return DueState.woche, 0
    return DueState.spaeter, 0


def task_sort_key(due: date | None, state: DueState, priority: Priority) -> tuple:
    return (DUE_STATE_RANK[state], due or date.max, PRIORITY_RANK[Priority(priority)])


# ------------------------------------------------------------- Fortschritt --
def effective_progress(status: TaskStatus, progress: int) -> int:
    s = TaskStatus(status)
    if s == TaskStatus.erledigt:
        return 100
    if s == TaskStatus.entfaellt:
        return 0
    return max(0, min(100, int(progress or 0)))


def round_tasks(tasks: list, round_id: int | None) -> list:
    """Aufgaben der angegebenen Runde. Ohne Runde (None) zählen alle. Aufgaben ohne round_id
    gelten als aktuelle Runde (Altbestand vor der Migration)."""
    if round_id is None:
        return list(tasks)
    return [t for t in tasks if getattr(t, "round_id", None) in (None, round_id)]


def project_progress(tasks: list, project_status: ProjectStatus) -> int:
    """tasks: Objekte mit status, progress, weight. Gewichtet, Entfällt zählt nicht."""
    relevant = [t for t in tasks if TaskStatus(t.status) != TaskStatus.entfaellt]
    if not relevant:
        return 100 if ProjectStatus(project_status) == ProjectStatus.abgeschlossen else 0
    total_w = sum(float(t.weight or 0) for t in relevant)
    if total_w <= 0:
        return 0
    done_w = sum(float(t.weight or 0) * effective_progress(t.status, t.progress) for t in relevant)
    return int(round(done_w / total_w))


# ---------------------------------------------------------------- Projekte --
def contractual_deadline(order_date: date | None, offered_weeks: float | None) -> date | None:
    if order_date is None or offered_weeks is None:
        return None
    return order_date + timedelta(days=int(round(float(offered_weeks) * 7)))


def effective_deadline(target: date | None, order_date: date | None, offered_weeks: float | None) -> date | None:
    return target or contractual_deadline(order_date, offered_weeks)


def project_is_active(status: ProjectStatus) -> bool:
    return ProjectStatus(status) in ACTIVE_PROJECT_STATUSES


@dataclass
class ProjectAssessment:
    signal: Signal
    reasons: list[str]            # warum rot/gelb
    warnings: list[str]           # Hinweise (ohne Bearbeiter, ohne Frist, ...)
    progress: int
    deadline: date | None
    remaining_workdays: int | None
    open_count: int
    task_count: int
    overdue_count: int
    next_task_id: int | None
    next_due: date | None
    next_task_title: str | None
    waiting_count: int


def assess_project(project, tasks: list, p: Params, round_id: int | None = None) -> ProjectAssessment:
    """project: Objekt mit status, assignee_id, order_date, offered_weeks, target_deadline.
    tasks: Objekte mit id, title, status, progress, weight, due_date, round_id.
    round_id: nur die Aufgaben dieser Runde zählen (Fortschritt, Ampel, Warnungen, nächste Frist)."""
    tasks = round_tasks(tasks, round_id)
    status = ProjectStatus(project.status)
    active = project_is_active(status)
    deadline = effective_deadline(project.target_deadline, project.order_date, project.offered_weeks)
    progress = project_progress(tasks, status)

    relevant = [t for t in tasks if TaskStatus(t.status) != TaskStatus.entfaellt]
    open_tasks = [t for t in tasks if task_is_open(t.status)]
    states = {t.id: due_state(t.status, t.due_date, p) for t in tasks}
    overdue = [t for t in open_tasks if states[t.id][0] == DueState.ueberfaellig]
    waiting = [t for t in open_tasks if TaskStatus(t.status) == TaskStatus.wartet]

    dated = sorted([t for t in open_tasks if t.due_date], key=lambda t: (t.due_date, t.sort_order, t.id))
    next_task = dated[0] if dated else (sorted(open_tasks, key=lambda t: (t.sort_order, t.id))[0] if open_tasks else None)

    remaining = None
    if active and deadline is not None:
        remaining = workdays_between(p.today, deadline, p.holidays)

    reasons: list[str] = []
    warnings: list[str] = []
    if status in CLOSED_PROJECT_STATUSES:
        signal = Signal.fertig
    elif not active:
        signal = Signal.grau
    else:
        if overdue:
            reasons.append(f"{len(overdue)} überfällige Aufgabe{'n' if len(overdue) > 1 else ''}")
        if deadline is not None and deadline < p.today:
            reasons.append(f"Projektfrist seit {(p.today - deadline).days} Tagen überschritten")
        if reasons:
            signal = Signal.rot
        else:
            soon = add_workdays(p.today, p.warn_workdays, p.holidays)
            soon_p = add_workdays(p.today, p.warn_project_workdays, p.holidays)
            if next_task is not None and next_task.due_date and next_task.due_date <= soon:
                reasons.append(f"nächste Frist {next_task.due_date.strftime('%d.%m.')}")
            if deadline is not None and deadline <= soon_p:
                reasons.append(f"Projektfrist {deadline.strftime('%d.%m.')}")
            signal = Signal.gelb if reasons else Signal.gruen

        if project.assignee_id is None:
            warnings.append("Kein Bearbeiter")
        if not open_tasks:
            warnings.append("Keine offene Aufgabe")
        if deadline is None:
            warnings.append("Keine Projektfrist")
        undated = [t for t in open_tasks if t.due_date is None]
        if undated:
            warnings.append(f"{len(undated)} Aufgabe{'n' if len(undated) > 1 else ''} ohne Frist")
        if deadline is not None:
            # Nachlaufende Aufgaben (Rechnung) dürfen kurz nach der Frist liegen: Toleranz 5 Arbeitstage
            tolerance = add_workdays(deadline, 5, p.holidays)
            late = [t for t in open_tasks if t.due_date and t.due_date > tolerance]
            if late:
                warnings.append(f"{len(late)} Aufgabe{'n' if len(late) > 1 else ''} deutlich nach der Projektfrist")
            # passen die offenen Aufgaben noch in die Restzeit? (grobe Schätzung: 1 Arbeitstag je offene Aufgabe)
            if remaining is not None and remaining > 0 and len(open_tasks) > remaining:
                warnings.append(f"{len(open_tasks)} offene Aufgaben, aber nur {remaining} Arbeitstag{'e' if remaining != 1 else ''} bis zur Frist")

    return ProjectAssessment(
        signal=signal, reasons=reasons, warnings=warnings, progress=progress, deadline=deadline,
        remaining_workdays=remaining, open_count=len(open_tasks), task_count=len(relevant),
        overdue_count=len(overdue), next_task_id=next_task.id if next_task else None,
        next_due=next_task.due_date if next_task else None,
        next_task_title=next_task.title if next_task else None, waiting_count=len(waiting),
    )


# ---------------------------------------------------------------- Vorlagen --
def template_due_dates(deadline: date | None, offsets: list[int | None], holidays: set[date],
                       today: date | None = None) -> list[date | None]:
    """Fristen rückwärts ab der Projektfrist. Passt der Vorlagen-Zeitraum nicht mehr in die
    verbleibenden Arbeitstage, werden die Offsets proportional gestaucht, damit keine Frist in
    der Vergangenheit liegt und die Reihenfolge erhalten bleibt."""
    if deadline is None:
        return [None for _ in offsets]
    factor = 1.0
    if today is not None:
        available = workdays_between(today, deadline, holidays)
        max_off = max([o for o in offsets if o is not None and o > 0], default=0)
        if max_off > 0 and available >= 0 and available < max_off:
            factor = available / max_off
    out: list[date | None] = []
    for off in offsets:
        if off is None:
            out.append(None)
        else:
            eff = int(round(off * factor)) if off > 0 else off
            out.append(add_workdays(deadline, -eff, holidays))
    return out
