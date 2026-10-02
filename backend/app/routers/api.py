"""Alle API-Routen. Die Logik liegt in den Services, hier nur Parameter und Antworten."""
from __future__ import annotations

import platform
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, models, schemas
from ..database import get_db
from ..services import admin, common, dashboard, notes, projects, tasks, views, outlook

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------- Meta --
@router.get("/meta", response_model=schemas.MetaOut)
def meta(db: Session = Depends(get_db)):
    return schemas.MetaOut(version=config.VERSION, **admin.meta_lists(), users=admin.list_users(db),
                           task_types=admin.list_task_types(db), templates=admin.list_templates(db),
                           settings=common.settings_out(db), platform=platform.system(),
                           can_open_folders=projects.can_open_folders())


@router.get("/dashboard", response_model=schemas.DashboardOut)
def get_dashboard(db: Session = Depends(get_db)):
    return dashboard.build(db)


@router.get("/notifications", response_model=list[schemas.NotificationOut])
def get_notifications(db: Session = Depends(get_db)):
    return dashboard.notifications(db)


@router.get("/search", response_model=schemas.SearchOut)
def search(q: str = "", db: Session = Depends(get_db)):
    return views.search(db, q)


@router.get("/calendar", response_model=list[schemas.CalendarDay])
def calendar(start: date, end: date, mine: bool = False, assignee_id: int | None = None, include_done: bool = False, db: Session = Depends(get_db)):
    return views.calendar(db, start, end, mine, assignee_id, include_done)


@router.get("/schedule", response_model=schemas.ScheduleOut)
def schedule(start: date | None = None, end: date | None = None, category: str | None = None, project_id: int | None = None,
             include_done: bool = False, db: Session = Depends(get_db)):
    return views.schedule(db, start, end, category, project_id, include_done)


# --------------------------------------------------------------- Projekte --
@router.get("/projects", response_model=list[schemas.ProjectOut])
def list_projects(status: str | None = None, active: bool | None = None, q: str = "", assignee_id: int | None = None,
                  signal: str | None = None, category: str | None = None, db: Session = Depends(get_db)):
    return projects.list_projects(db, status, active, q, assignee_id, signal, category)


@router.post("/projects", response_model=schemas.ProjectDetail, status_code=201)
def create_project(data: schemas.ProjectCreate, db: Session = Depends(get_db)):
    return projects.create_project(db, data)


@router.get("/projects/folder-lookup")
def folder_lookup(project_number: str = "", status: str = "anfrage", name: str = "", db: Session = Depends(get_db)):
    return projects.folder_lookup(db, project_number, status, name)


@router.get("/projects/{project_id}", response_model=schemas.ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return projects.get_project(db, project_id)


@router.put("/projects/{project_id}", response_model=schemas.ProjectDetail)
def update_project(project_id: int, data: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    return projects.update_project(db, project_id, data)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    projects.delete_project(db, project_id)
    return Response(status_code=204)


@router.post("/projects/{project_id}/follow-up", response_model=schemas.ProjectDetail)
def follow_up(project_id: int, data: schemas.FollowUpIn, db: Session = Depends(get_db)):
    return projects.start_follow_up(db, project_id, data)


@router.post("/projects/{project_id}/complete", response_model=schemas.ProjectDetail)
def complete_project(project_id: int, data: schemas.CompleteProject, db: Session = Depends(get_db)):
    return projects.complete_project(db, project_id, data.open_tasks)


@router.post("/projects/{project_id}/apply-template", response_model=schemas.ProjectDetail)
def apply_template(project_id: int, data: schemas.ApplyTemplate, db: Session = Depends(get_db)):
    return projects.apply_template_endpoint(db, project_id, data.template_id, data.deadline, data.compute_due_dates)


@router.post("/projects/{project_id}/open-folder")
def open_folder(project_id: int, db: Session = Depends(get_db)):
    return projects.open_folder(db, project_id)


@router.put("/projects/{project_id}/tasks/order", response_model=list[schemas.TaskOut])
def reorder(project_id: int, data: schemas.TaskReorder, db: Session = Depends(get_db)):
    return tasks.reorder_tasks(db, project_id, data.task_ids)


@router.get("/projects/{project_id}/notes", response_model=list[schemas.NoteOut])
def project_notes(project_id: int, db: Session = Depends(get_db)):
    return notes.list_notes(db, project_id=project_id)


@router.get("/projects/{project_id}/activity", response_model=list[schemas.ActivityOut])
def project_activity(project_id: int, limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(models.ActivityLog).where(models.ActivityLog.project_id == project_id)
                      .order_by(models.ActivityLog.created_at.desc(), models.ActivityLog.id.desc()).limit(limit)).all()
    return [common.activity_out(a) for a in rows]


# ---------------------------------------------------------------- Aufgaben --
@router.get("/tasks", response_model=list[schemas.TaskOut])
def list_tasks(assignee_id: int | None = None, mine: bool = False, project_id: int | None = None, status: str | None = None,
               open_only: bool = True, bucket: str | None = None, priority: str | None = None, task_type_id: int | None = None,
               q: str = "", category: str | None = None, limit: int | None = None, db: Session = Depends(get_db)):
    return tasks.list_tasks(db, assignee_id, mine, project_id, status, open_only, bucket, priority, task_type_id, q, category, limit)


@router.post("/tasks", response_model=schemas.TaskOut, status_code=201)
def create_task(data: schemas.TaskCreate, db: Session = Depends(get_db)):
    return tasks.create_task(db, data)


@router.get("/tasks/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    return tasks.get_task(db, task_id)


@router.put("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, data: schemas.TaskUpdate, db: Session = Depends(get_db)):
    return tasks.update_task(db, task_id, data)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    tasks.delete_task(db, task_id)
    return Response(status_code=204)


@router.post("/tasks/{task_id}/complete", response_model=schemas.TaskOut)
def complete_task(task_id: int, db: Session = Depends(get_db)):
    return tasks.complete_task(db, task_id)


@router.post("/tasks/{task_id}/reopen", response_model=schemas.TaskOut)
def reopen_task(task_id: int, db: Session = Depends(get_db)):
    return tasks.reopen_task(db, task_id)


@router.post("/tasks/{task_id}/shift", response_model=schemas.TaskOut)
def shift_task(task_id: int, workdays: int = Query(..., ge=-60, le=60), db: Session = Depends(get_db)):
    return tasks.shift_due(db, task_id, workdays)


@router.get("/tasks/{task_id}/notes", response_model=list[schemas.NoteOut])
def task_notes(task_id: int, db: Session = Depends(get_db)):
    return notes.list_notes(db, task_id=task_id)


# ----------------------------------------------------------------- Notizen --
@router.get("/notes", response_model=list[schemas.NoteOut])
def list_notes(project_id: int | None = None, task_id: int | None = None, limit: int = 200, db: Session = Depends(get_db)):
    return notes.list_notes(db, project_id, task_id, limit)


@router.post("/notes", response_model=schemas.NoteOut, status_code=201)
def create_note(data: schemas.NoteCreate, db: Session = Depends(get_db)):
    return notes.create_note(db, data)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    notes.delete_note(db, note_id)
    return Response(status_code=204)


# ------------------------------------------------------------- Aktivitäten --
@router.get("/activity", response_model=list[schemas.ActivityOut])
def activity(limit: int = 200, project_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(models.ActivityLog).order_by(models.ActivityLog.created_at.desc(), models.ActivityLog.id.desc())
    if project_id:
        stmt = stmt.where(models.ActivityLog.project_id == project_id)
    return [common.activity_out(a) for a in db.scalars(stmt.limit(limit)).all()]


# ---------------------------------------------------------------- Vorlagen --
@router.get("/templates", response_model=list[schemas.TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    return admin.list_templates(db)


@router.post("/templates", response_model=schemas.TemplateOut, status_code=201)
def create_template(data: schemas.TemplateIn, db: Session = Depends(get_db)):
    return admin.save_template(db, data)


@router.put("/templates/{template_id}", response_model=schemas.TemplateOut)
def update_template(template_id: int, data: schemas.TemplateIn, db: Session = Depends(get_db)):
    return admin.save_template(db, data, template_id)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    admin.delete_template(db, template_id)
    return Response(status_code=204)


@router.get("/templates/{template_id}/preview", response_model=list[schemas.TemplatePreviewRow])
def preview_template(template_id: int, deadline: date | None = None, db: Session = Depends(get_db)):
    return admin.preview_template(db, template_id, deadline)


# -------------------------------------------------------------- Bearbeiter --
@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return admin.list_users(db)


@router.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(data: schemas.UserIn, db: Session = Depends(get_db)):
    return admin.save_user(db, data)


@router.put("/users/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: int, data: schemas.UserIn, db: Session = Depends(get_db)):
    return admin.save_user(db, data, user_id)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    admin.delete_user(db, user_id)
    return Response(status_code=204)


# ------------------------------------------------------------ Aufgabenarten --
@router.get("/task-types", response_model=list[schemas.TaskTypeOut])
def list_task_types(db: Session = Depends(get_db)):
    return admin.list_task_types(db)


@router.post("/task-types", response_model=schemas.TaskTypeOut, status_code=201)
def create_task_type(data: schemas.TaskTypeIn, db: Session = Depends(get_db)):
    return admin.save_task_type(db, data)


@router.put("/task-types/{type_id}", response_model=schemas.TaskTypeOut)
def update_task_type(type_id: int, data: schemas.TaskTypeIn, db: Session = Depends(get_db)):
    return admin.save_task_type(db, data, type_id)


@router.delete("/task-types/{type_id}", status_code=204)
def delete_task_type(type_id: int, db: Session = Depends(get_db)):
    admin.delete_task_type(db, type_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- Feiertage --
@router.get("/holidays", response_model=list[schemas.HolidayOut])
def list_holidays(db: Session = Depends(get_db)):
    return admin.list_holidays(db)


@router.post("/holidays", response_model=schemas.HolidayOut, status_code=201)
def add_holiday(data: schemas.HolidayIn, db: Session = Depends(get_db)):
    return admin.add_holiday(db, data)


@router.delete("/holidays/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: int, db: Session = Depends(get_db)):
    admin.delete_holiday(db, holiday_id)
    return Response(status_code=204)


# ------------------------------------------------------------ Einstellungen --
@router.get("/settings", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return common.settings_out(db)


@router.put("/settings", response_model=schemas.SettingsOut)
def put_settings(data: schemas.SettingsIn, db: Session = Depends(get_db)):
    return admin.update_settings(db, data)


# --------------------------------------------------------- Export / Backup --
@router.get("/export/excel")
def export_excel(db: Session = Depends(get_db)):
    data = admin.export_excel(db)
    name = f"Projekte_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    return StreamingResponse(iter([data]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export/csv")
def export_csv(what: str = "tasks", db: Session = Depends(get_db)):
    text = admin.export_csv(db, what)
    name = f"{'Projekte' if what == 'projects' else 'Aufgaben'}_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(content="﻿" + text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/outlook/sync", response_model=schemas.OutlookSyncOut)
def outlook_sync(db: Session = Depends(get_db)):
    try:
        return outlook.run_sync(db, manual=True)
    except outlook.OutlookError as e:
        raise HTTPException(503, str(e))


@router.post("/outlook/clear", response_model=schemas.OutlookSyncOut)
def outlook_clear(db: Session = Depends(get_db)):
    try:
        return outlook.clear(db)
    except outlook.OutlookError as e:
        raise HTTPException(503, str(e))


@router.get("/backups", response_model=list[schemas.BackupOut])
def list_backups():
    return admin.list_backups()


@router.post("/backups", response_model=schemas.BackupOut, status_code=201)
def create_backup():
    return admin.create_backup()
