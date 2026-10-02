from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .enums import Priority, ProjectCategory, ProjectStatus, TaskStatus


def _now() -> datetime:
    return datetime.now()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[str] = mapped_column(String(100), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TaskType(Base):
    __tablename__ = "task_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    default_weight: Mapped[float] = mapped_column(Float, default=1.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    client: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[ProjectCategory] = mapped_column(String(20), default=ProjectCategory.gutachten, index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    participants: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[ProjectStatus] = mapped_column(String(30), default=ProjectStatus.anfrage, index=True)
    priority: Mapped[Priority] = mapped_column(String(20), default=Priority.normal)
    request_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    offer_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    offered_weeks: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    folder_path: Mapped[str] = mapped_column(Text, default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    assignee: Mapped[User | None] = relationship("User", lazy="joined")
    tasks: Mapped[list[Task]] = relationship("Task", back_populates="project", cascade="all, delete-orphan", order_by="Task.sort_order, Task.id")
    notes: Mapped[list[Note]] = relationship("Note", back_populates="project", cascade="all, delete-orphan")
    rounds: Mapped[list[ProjectRound]] = relationship("ProjectRound", back_populates="project", cascade="all, delete-orphan", order_by="ProjectRound.number")


class ProjectRound(Base):
    """Durchgang eines Projekts: Runde 1 ist der Erstauftrag, jeder Folgeauftrag (z. B. Planänderung) eine weitere Runde.
    Die Projektfelder status, Daten und Frist spiegeln immer die aktuelle Runde (höchste Nummer)."""
    __tablename__ = "project_rounds"
    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_round_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200), default="Erstauftrag")
    status: Mapped[ProjectStatus] = mapped_column(String(30), default=ProjectStatus.anfrage)
    request_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    offer_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    offered_weeks: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[Project] = relationship("Project", back_populates="rounds")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    task_type_id: Mapped[int | None] = mapped_column(ForeignKey("task_types.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[TaskStatus] = mapped_column(String(30), default=TaskStatus.nicht_begonnen, index=True)
    priority: Mapped[Priority] = mapped_column(String(20), default=Priority.normal)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    predecessor_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    waiting_for: Mapped[str] = mapped_column(String(200), default="")
    waiting_on: Mapped[str] = mapped_column(String(200), default="")
    waiting_since: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminder_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)   # geplant am, die Frist bleibt due_date
    round_id: Mapped[int | None] = mapped_column(ForeignKey("project_rounds.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    project: Mapped[Project] = relationship("Project", back_populates="tasks")
    assignee: Mapped[User | None] = relationship("User", lazy="joined")
    task_type: Mapped[TaskType | None] = relationship("TaskType", lazy="joined")


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    project: Mapped[Project] = relationship("Project", back_populates="notes")
    author: Mapped[User | None] = relationship("User", lazy="joined")
    task: Mapped[Task | None] = relationship("Task", lazy="joined")


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    field: Mapped[str] = mapped_column(String(60), default="")
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    project: Mapped[Project | None] = relationship("Project", lazy="joined")
    task: Mapped[Task | None] = relationship("Task", lazy="joined")
    user: Mapped[User | None] = relationship("User", lazy="joined")


class ProjectTemplate(Base):
    __tablename__ = "project_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[ProjectCategory | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    tasks: Mapped[list[TemplateTask]] = relationship("TemplateTask", back_populates="template", cascade="all, delete-orphan", order_by="TemplateTask.sort_order")


class TemplateTask(Base):
    __tablename__ = "template_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("project_templates.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200))
    task_type_id: Mapped[int | None] = mapped_column(ForeignKey("task_types.id", ondelete="SET NULL"), nullable=True)
    offset_workdays: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Arbeitstage vor Projektfrist, negativ = danach
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    assignee_role: Mapped[str] = mapped_column(String(20), default="PL")  # PL = Projektleiter, sonst Kürzel
    depends_on_previous: Mapped[bool] = mapped_column(Boolean, default=False)

    template: Mapped[ProjectTemplate] = relationship("ProjectTemplate", back_populates="tasks")
    task_type: Mapped[TaskType | None] = relationship("TaskType", lazy="joined")


class Holiday(Base):
    __tablename__ = "holidays"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True)
    name: Mapped[str] = mapped_column(String(100))


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
