export type ProjectStatus = 'anfrage' | 'angebot' | 'beauftragt' | 'in_bearbeitung' | 'wartet_kunde' | 'interne_pruefung' | 'abgeschlossen' | 'auf_eis' | 'abgelehnt'
export type TaskStatus = 'nicht_begonnen' | 'geplant' | 'in_bearbeitung' | 'wartet' | 'erledigt' | 'entfaellt'
export type Priority = 'niedrig' | 'normal' | 'hoch' | 'kritisch'
export type Category = 'wea' | 'messung' | 'gutachten' | 'intern'
export type DueState = 'erledigt' | 'ohne_frist' | 'ueberfaellig' | 'heute' | 'demnaechst' | 'woche' | 'spaeter'
export type Signal = 'rot' | 'gelb' | 'gruen' | 'grau' | 'fertig'

export interface User { id: number; code: string; name: string; role: string; active: boolean; sort_order: number }
export interface TaskType { id: number; name: string; default_weight: number; sort_order: number; active: boolean }

export interface Task {
  id: number; project_id: number; project_number: string; project_name: string
  title: string; task_type_id: number | null; task_type_name: string | null; description: string
  assignee_id: number | null; assignee_code: string | null
  status: TaskStatus; priority: Priority
  start_date: string | null; due_date: string | null; completed_at: string | null
  progress: number; weight: number; predecessor_id: number | null; predecessor_open: boolean; sort_order: number
  waiting_for: string; waiting_on: string; waiting_since: string | null; reminder_date: string | null
  created_at: string; updated_at: string
  round_id: number | null
  due_state: DueState; days_overdue: number; kw: number | null; is_open: boolean
  round_number: number; is_current_round: boolean
}

export interface Project {
  id: number; project_number: string; name: string; client: string; category: Category
  assignee_id: number | null; assignee_code: string | null; participants: string
  status: ProjectStatus; priority: Priority
  request_date: string | null; offer_date: string | null; order_date: string | null
  offered_weeks: number | null; target_deadline: string | null; completed_at: string | null
  folder_path: string; remarks: string; created_at: string; updated_at: string
  is_active: boolean; contractual_deadline: string | null; deadline: string | null; deadline_kw: number | null
  remaining_workdays: number | null; progress: number; signal: Signal; reasons: string[]; warnings: string[]
  task_count: number; open_count: number; overdue_count: number; waiting_count: number
  next_task_id: number | null; next_task_title: string | null; next_due: string | null
  expected_folder_name: string; folder_matches: boolean
  round_number: number; round_title: string
}

export interface Round {
  id: number; project_id: number; number: number; title: string; status: ProjectStatus
  request_date: string | null; offer_date: string | null; order_date: string | null; offered_weeks: number | null; target_deadline: string | null
  closed_at: string | null; created_at: string; task_count: number; open_count: number; progress: number
}

export interface ProjectDetail extends Project { tasks: Task[]; notes: Note[]; rounds: Round[]; folder_note: string | null }

export interface Note {
  id: number; project_id: number; project_number: string; task_id: number | null; task_title: string | null
  author_id: number | null; author_code: string | null; content: string; created_at: string
}

export interface Activity {
  id: number; project_id: number | null; project_number: string | null; task_id: number | null; task_title: string | null
  user_code: string | null; action: string; field: string; old_value: string; new_value: string; details: string; created_at: string
}

export interface TemplateTask {
  id?: number; sort_order?: number; title: string; task_type_id: number | null; task_type_name?: string | null
  offset_workdays: number | null; weight: number | null; assignee_role: string; depends_on_previous: boolean
}
export interface Template { id: number; name: string; description: string; category: Category | null; sort_order: number; tasks: TemplateTask[] }
export interface TemplatePreviewRow { title: string; task_type_name: string | null; offset_workdays: number | null; due_date: string | null; weight: number | null; assignee_role: string }

export interface Holiday { id: number; date: string; name: string }

export interface Settings {
  my_user_id: number | null; my_user_code: string | null; base_path: string
  warn_workdays: number; warn_project_workdays: number; auto_backup: boolean
  dashboard_widgets: Record<string, boolean>
}

export interface Option { value: string; label: string; active?: boolean; open?: boolean }

export interface Meta {
  version: string
  project_categories: Option[]; project_statuses: Option[]; task_statuses: Option[]; priorities: Option[]; due_states: Option[]; signals: Option[]
  users: User[]; task_types: TaskType[]; templates: Template[]; settings: Settings; platform: string; can_open_folders: boolean
}

export interface AttentionItem {
  kind: 'task' | 'project'; level: 'rot' | 'orange' | 'gelb' | 'blau'; title: string; subtitle: string; reason: string
  task_id: number | null; project_id: number | null; project_number: string | null; due_date: string | null
}

export interface Dashboard {
  today: string; greeting_name: string; kw: number
  counts: { today: number; overdue: number; this_week: number; next_week: number; soon: number; active_projects: number; critical_projects: number
    waiting_tasks: number; waiting_projects: number; inquiries: number; offers: number; my_open: number; others_open: number; no_due: number }
  attention: AttentionItem[]; today_tasks: Task[]; overdue_tasks: Task[]; upcoming: Task[]; waiting: Task[]
  projects_attention: Project[]; active_projects: Project[]; recent_activity: Activity[]; widgets: Record<string, boolean>
}

export interface SearchResult { projects: Project[]; tasks: Task[]; notes: Note[] }
export interface Notification { level: string; text: string; task_id: number | null; project_id: number | null }
export interface CalendarDay { date: string; kw: number; is_workday: boolean; holiday: string | null; tasks: Task[] }
export interface ScheduleTask { id: number; title: string; status: TaskStatus; due_state: DueState; start: string; end: string; assignee_code: string | null; predecessor_open: boolean }
export interface ScheduleProject { id: number; project_number: string; name: string; signal: Signal; deadline: string | null; progress: number; tasks: ScheduleTask[] }
export interface Schedule { start: string; end: string; today: string; projects: ScheduleProject[]; holidays: Holiday[] }
export interface Backup { file: string; size_bytes: number; created_at: string }
