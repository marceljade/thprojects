from datetime import date
from app import scheduling as s
from app.enums import DueState, TaskStatus, ProjectStatus, Signal, Priority
from types import SimpleNamespace as NS

H = {date(2026, 10, 3)}
P = s.Params(today=date(2026, 10, 1), holidays=H, warn_workdays=3, warn_project_workdays=5)

def test_workdays():
    assert s.add_workdays(date(2026, 10, 1), 1, H) == date(2026, 10, 2)
    assert s.add_workdays(date(2026, 10, 2), 1, H) == date(2026, 10, 5)   # Sa, So überspringen
    assert s.add_workdays(date(2026, 10, 9), -5, H) == date(2026, 10, 2)
    assert s.workdays_between(date(2026, 10, 1), date(2026, 10, 8), H) == 5
    assert s.workdays_between(date(2026, 10, 8), date(2026, 10, 1), H) == -5
    assert s.iso_week(date(2026, 10, 8)) == (2026, 41)

def test_due_state():
    assert s.due_state(TaskStatus.erledigt, date(2020, 1, 1), P) == (DueState.erledigt, 0)
    assert s.due_state(TaskStatus.nicht_begonnen, None, P) == (DueState.ohne_frist, 0)
    assert s.due_state(TaskStatus.in_bearbeitung, date(2026, 9, 28), P) == (DueState.ueberfaellig, 3)
    assert s.due_state(TaskStatus.wartet, date(2026, 10, 1), P)[0] == DueState.heute
    assert s.due_state(TaskStatus.geplant, date(2026, 10, 6), P)[0] == DueState.demnaechst
    assert s.due_state(TaskStatus.geplant, date(2026, 10, 8), P)[0] == DueState.woche
    assert s.due_state(TaskStatus.geplant, date(2026, 10, 20), P)[0] == DueState.spaeter

def _t(i, status, due=None, w=1, prog=0):
    return NS(id=i, title=f"T{i}", status=status, due_date=due, weight=w, progress=prog, sort_order=i)

def test_progress():
    tasks = [_t(1, TaskStatus.erledigt, w=3), _t(2, TaskStatus.in_bearbeitung, w=5, prog=60), _t(3, TaskStatus.entfaellt, w=100), _t(4, TaskStatus.nicht_begonnen, w=2)]
    assert s.project_progress(tasks, ProjectStatus.in_bearbeitung) == round((300 + 300) / 10)
    assert s.project_progress([], ProjectStatus.abgeschlossen) == 100
    assert s.project_progress([], ProjectStatus.in_bearbeitung) == 0

def test_assess():
    pr = NS(status=ProjectStatus.in_bearbeitung, assignee_id=1, order_date=date(2026, 9, 7), offered_weeks=4, target_deadline=None)
    a = s.assess_project(pr, [_t(1, TaskStatus.erledigt, date(2026, 9, 20)), _t(2, TaskStatus.nicht_begonnen, date(2026, 10, 2))], P)
    assert a.deadline == date(2026, 10, 5)
    assert a.signal == Signal.gelb and a.overdue_count == 0 and a.next_task_id == 2
    a = s.assess_project(pr, [_t(2, TaskStatus.nicht_begonnen, date(2026, 9, 25))], P)
    assert a.signal == Signal.rot and "überfällig" in a.reasons[0]
    a = s.assess_project(NS(status=ProjectStatus.angebot, assignee_id=None, order_date=None, offered_weeks=None, target_deadline=None), [], P)
    assert a.signal == Signal.grau and a.warnings == []
    a = s.assess_project(NS(status=ProjectStatus.abgeschlossen, assignee_id=None, order_date=None, offered_weeks=None, target_deadline=None), [], P)
    assert a.signal == Signal.fertig and a.progress == 100
