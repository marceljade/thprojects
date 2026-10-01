from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..schemas import NoteCreate, NoteOut
from . import common


def add_note_obj(db: Session, project_id: int, task_id: int | None, content: str, author_id: int | None = None) -> models.Note:
    if author_id is None:
        me = common.my_user(db)
        author_id = me.id if me else None
    n = models.Note(project_id=project_id, task_id=task_id, author_id=author_id, content=content.strip())
    db.add(n)
    db.flush()
    common.log(db, "Notiz hinzugefügt", project_id=project_id, task_id=task_id, field="notiz", new=content.strip()[:80])
    pr = db.get(models.Project, project_id)
    if pr:
        common.touch(pr)
    return n


def create_note(db: Session, data: NoteCreate) -> NoteOut:
    pr = db.get(models.Project, data.project_id)
    if pr is None:
        raise HTTPException(422, "Das gewählte Projekt existiert nicht.")
    if data.task_id is not None:
        t = db.get(models.Task, data.task_id)
        if t is None or t.project_id != pr.id:
            raise HTTPException(422, "Die Aufgabe gehört nicht zu diesem Projekt.")
    n = add_note_obj(db, data.project_id, data.task_id, data.content, data.author_id)
    db.commit()
    db.refresh(n)
    return common.note_out(n)


def list_notes(db: Session, project_id: int | None = None, task_id: int | None = None, limit: int = 200) -> list[NoteOut]:
    stmt = select(models.Note).order_by(models.Note.created_at.desc(), models.Note.id.desc())
    if project_id:
        stmt = stmt.where(models.Note.project_id == project_id)
    if task_id:
        stmt = stmt.where(models.Note.task_id == task_id)
    return [common.note_out(n) for n in db.scalars(stmt.limit(limit)).all()]


def delete_note(db: Session, note_id: int) -> None:
    n = db.get(models.Note, note_id)
    if n is None:
        raise HTTPException(404, "Notiz nicht gefunden.")
    common.log(db, "Notiz gelöscht", project_id=n.project_id, task_id=n.task_id, details=n.content[:80])
    db.delete(n)
    db.commit()
