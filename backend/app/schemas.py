from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import DueState, Priority, ProjectCategory, ProjectStatus, Signal, TaskStatus


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------- Users --
class UserOut(ORM):
    id: int
    code: str
    name: str
    role: str
    active: bool
    sort_order: int


class UserIn(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = ""
    role: str = ""
    active: bool = True
    sort_order: int = 0

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        return v.strip().upper()


class TaskTypeOut(ORM):
    id: int
    name: str
    default_weight: float
    sort_order: int
    active: bool


class TaskTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    default_weight: float = 1.0
    sort_order: int = 0
    active: bool = True


# ------------------------------------------------------------------- Tasks --
class TaskOut(ORM):
    id: int
    project_id: int
    project_number: str
    project_name: str
    title: str
    task_type_id: int | None
    task_type_name: str | None
    description: str
    assignee_id: int | None
    assignee_code: str | None
    status: TaskStatus
    priority: Priority
    start_date: date | None
    due_date: date | None
    completed_at: date | None
    progress: int
    weight: float
    predecessor_id: int | None
    predecessor_open: bool
    sort_order: int
    waiting_for: str
    waiting_on: str
    waiting_since: date | None
    reminder_date: date | None
    planned_date: date | None
    created_at: datetime
    updated_at: datetime
    round_id: int | None
    # berechnet
    due_state: DueState
    calendar_date: date | None
    planned_after_due: bool
    warnings: list[str]
    is_today: bool
    days_overdue: int
    kw: int | None
    is_open: bool
    round_number: int
    is_current_round: bool


class TaskCreate(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=200)
    task_type_id: int | None = None
    description: str = ""
    assignee_id: int | None = None
    status: TaskStatus = TaskStatus.nicht_begonnen
    priority: Priority = Priority.normal
    start_date: date | None = None
    due_date: date | None = None
    progress: int = Field(default=0, ge=0, le=100)
    weight: float | None = None
    predecessor_id: int | None = None
    waiting_for: str = ""
    waiting_on: str = ""
    waiting_since: date | None = None
    reminder_date: date | None = None
    note: str = ""


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    task_type_id: int | None = None
    description: str | None = None
    assignee_id: int | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    start_date: date | None = None
    due_date: date | None = None
    completed_at: date | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    weight: float | None = None
    predecessor_id: int | None = None
    sort_order: int | None = None
    waiting_for: str | None = None
    waiting_on: str | None = None
    waiting_since: date | None = None
    reminder_date: date | None = None
    planned_date: date | None = None
    # Felder, die explizit auf NULL gesetzt werden sollen
    clear: list[str] = Field(default_factory=list)


class TaskReorder(BaseModel):
    task_ids: list[int]


class TaskPlanIn(BaseModel):
    planned_date: date | None = None   # None = Planung aufheben


# ---------------------------------------------------------------- Projects --
class ProjectOut(ORM):
    id: int
    project_number: str
    name: str
    client: str
    category: ProjectCategory
    assignee_id: int | None
    assignee_code: str | None
    participants: str
    status: ProjectStatus
    priority: Priority
    request_date: date | None
    offer_date: date | None
    order_date: date | None
    offered_weeks: float | None
    target_deadline: date | None
    completed_at: date | None
    folder_path: str
    remarks: str
    created_at: datetime
    updated_at: datetime
    # berechnet
    is_active: bool
    contractual_deadline: date | None
    deadline: date | None
    deadline_kw: int | None
    remaining_workdays: int | None
    progress: int
    signal: Signal
    reasons: list[str]
    warnings: list[str]
    task_count: int
    open_count: int
    overdue_count: int
    waiting_count: int
    next_task_id: int | None
    next_task_title: str | None
    next_due: date | None
    expected_folder_name: str
    folder_matches: bool
    round_number: int
    round_title: str


class RoundOut(ORM):
    id: int
    project_id: int
    number: int
    title: str
    status: ProjectStatus
    request_date: date | None
    offer_date: date | None
    order_date: date | None
    offered_weeks: float | None
    target_deadline: date | None
    closed_at: date | None
    created_at: datetime
    task_count: int
    open_count: int
    progress: int


class ProjectDetail(ProjectOut):
    tasks: list[TaskOut]
    notes: list[NoteOut]
    rounds: list[RoundOut]
    folder_note: str | None = None


class FollowUpIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    status: ProjectStatus = ProjectStatus.anfrage
    request_date: date | None = None
    template_id: int | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: ProjectStatus) -> ProjectStatus:
        if v not in (ProjectStatus.anfrage, ProjectStatus.angebot):
            raise ValueError("Ein Folgeauftrag beginnt als Anfrage oder Angebot.")
        return v


class ProjectCreate(BaseModel):
    project_number: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=200)
    client: str = ""
    category: ProjectCategory = ProjectCategory.gutachten
    assignee_id: int | None = None
    participants: str = ""
    status: ProjectStatus = ProjectStatus.anfrage
    priority: Priority = Priority.normal
    request_date: date | None = None
    offer_date: date | None = None
    order_date: date | None = None
    offered_weeks: float | None = None
    target_deadline: date | None = None
    folder_path: str = ""
    remarks: str = ""
    template_id: int | None = None
    compute_due_dates: bool = True

    @field_validator("project_number")
    @classmethod
    def _nr(cls, v: str) -> str:
        return v.strip()


class ProjectUpdate(BaseModel):
    project_number: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = None
    client: str | None = None
    category: ProjectCategory | None = None
    assignee_id: int | None = None
    participants: str | None = None
    status: ProjectStatus | None = None
    priority: Priority | None = None
    request_date: date | None = None
    offer_date: date | None = None
    order_date: date | None = None
    offered_weeks: float | None = None
    target_deadline: date | None = None
    completed_at: date | None = None
    folder_path: str | None = None
    remarks: str | None = None
    clear: list[str] = Field(default_factory=list)


class ApplyTemplate(BaseModel):
    template_id: int
    deadline: date | None = None
    compute_due_dates: bool = True


class CompleteProject(BaseModel):
    open_tasks: str = "erledigt"  # erledigt | entfaellt | behalten


# ------------------------------------------------------------------- Notes --
class NoteOut(ORM):
    id: int
    project_id: int
    project_number: str
    task_id: int | None
    task_title: str | None
    author_id: int | None
    author_code: str | None
    content: str
    created_at: datetime


class NoteCreate(BaseModel):
    project_id: int
    task_id: int | None = None
    content: str = Field(min_length=1)
    author_id: int | None = None


# ---------------------------------------------------------------- Activity --
class ActivityOut(ORM):
    id: int
    project_id: int | None
    project_number: str | None
    task_id: int | None
    task_title: str | None
    user_code: str | None
    action: str
    field: str
    old_value: str
    new_value: str
    details: str
    created_at: datetime


# --------------------------------------------------------------- Templates --
class TemplateTaskOut(ORM):
    id: int
    sort_order: int
    title: str
    task_type_id: int | None
    task_type_name: str | None
    offset_workdays: int | None
    weight: float | None
    assignee_role: str
    depends_on_previous: bool


class TemplateTaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    task_type_id: int | None = None
    offset_workdays: int | None = None
    weight: float | None = None
    assignee_role: str = "PL"
    depends_on_previous: bool = False


class TemplateOut(ORM):
    id: int
    name: str
    description: str
    category: ProjectCategory | None
    sort_order: int
    tasks: list[TemplateTaskOut]


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    category: ProjectCategory | None = None
    sort_order: int = 0
    tasks: list[TemplateTaskIn] = Field(default_factory=list)


class TemplatePreviewRow(BaseModel):
    title: str
    task_type_name: str | None
    offset_workdays: int | None
    due_date: date | None
    weight: float | None
    assignee_role: str


# ---------------------------------------------------------------- Holidays --
class HolidayOut(ORM):
    id: int
    date: date
    name: str


class HolidayIn(BaseModel):
    date: date
    name: str = ""


# ---------------------------------------------------------------- Settings --
class SettingsOut(BaseModel):
    my_user_id: int | None
    my_user_code: str | None
    base_path: str
    warn_workdays: int
    warn_project_workdays: int
    auto_backup: bool
    dashboard_widgets: dict[str, bool]
    outlook_sync: str                    # aus | manuell | automatisch
    outlook_last_sync: datetime | None
    outlook_last_result: str


class SettingsIn(BaseModel):
    my_user_id: int | None = None
    base_path: str | None = None
    warn_workdays: int | None = Field(default=None, ge=0, le=30)
    warn_project_workdays: int | None = Field(default=None, ge=0, le=60)
    auto_backup: bool | None = None
    dashboard_widgets: dict[str, bool] | None = None
    outlook_sync: str | None = None

    @field_validator("outlook_sync")
    @classmethod
    def _outlook(cls, v: str | None) -> str | None:
        if v is not None and v not in ("aus", "manuell", "automatisch"):
            raise ValueError("outlook_sync muss aus, manuell oder automatisch sein.")
        return v


class OutlookSyncOut(BaseModel):
    created: int
    updated: int
    removed: int
    total: int
    at: datetime
    message: str


# --------------------------------------------------------------- Dashboard --
class DashboardCounts(BaseModel):
    today: int
    overdue: int
    this_week: int
    next_week: int
    soon: int
    active_projects: int
    critical_projects: int
    waiting_tasks: int
    waiting_projects: int
    inquiries: int
    offers: int
    my_open: int
    others_open: int
    no_due: int


class AttentionItem(BaseModel):
    kind: str          # task | project
    level: str         # rot | orange | gelb | blau
    title: str
    subtitle: str
    reason: str
    task_id: int | None = None
    project_id: int | None = None
    project_number: str | None = None
    due_date: date | None = None


class DashboardOut(BaseModel):
    today: date
    greeting_name: str
    kw: int
    counts: DashboardCounts
    attention: list[AttentionItem]
    today_tasks: list[TaskOut]
    overdue_tasks: list[TaskOut]
    upcoming: list[TaskOut]
    waiting: list[TaskOut]
    projects_attention: list[ProjectOut]
    active_projects: list[ProjectOut]
    recent_activity: list[ActivityOut]
    widgets: dict[str, bool]


class SearchOut(BaseModel):
    projects: list[ProjectOut]
    tasks: list[TaskOut]
    notes: list[NoteOut]


class NotificationOut(BaseModel):
    level: str
    text: str
    task_id: int | None = None
    project_id: int | None = None


class CalendarMark(BaseModel):
    """Nicht verschiebbare Markierung im Kalender: Frist einer anderswo geplanten Aufgabe oder Projektfrist."""
    kind: str                 # due | project
    task_id: int | None = None
    project_id: int
    project_number: str
    title: str


class CalendarDay(BaseModel):
    date: date
    kw: int
    is_workday: bool
    holiday: str | None
    tasks: list[TaskOut]
    marks: list[CalendarMark] = Field(default_factory=list)


class ScheduleTask(BaseModel):
    id: int
    title: str
    status: TaskStatus
    due_state: DueState
    start: date
    end: date
    assignee_code: str | None
    predecessor_open: bool


class ScheduleProject(BaseModel):
    id: int
    project_number: str
    name: str
    signal: Signal
    deadline: date | None
    progress: int
    tasks: list[ScheduleTask]


class ScheduleOut(BaseModel):
    start: date
    end: date
    today: date
    projects: list[ScheduleProject]
    holidays: list[HolidayOut]


class BackupOut(BaseModel):
    file: str
    size_bytes: int
    created_at: datetime


class MetaOut(BaseModel):
    version: str
    project_categories: list[dict]
    project_statuses: list[dict]
    task_statuses: list[dict]
    priorities: list[dict]
    due_states: list[dict]
    signals: list[dict]
    users: list[UserOut]
    task_types: list[TaskTypeOut]
    templates: list[TemplateOut]
    settings: SettingsOut
    platform: str
    can_open_folders: bool
