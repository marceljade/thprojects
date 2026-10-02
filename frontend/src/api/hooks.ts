import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, qs } from './client'
import type { Activity, Backup, CalendarDay, Dashboard, Holiday, Meta, Note, Notification, Project, ProjectDetail, Schedule, SearchResult, Settings, Task, TaskType, Template, TemplatePreviewRow, User } from './types'

export const keys = {
  meta: ['meta'] as const,
  dashboard: ['dashboard'] as const,
  notifications: ['notifications'] as const,
  projects: (p: Record<string, unknown>) => ['projects', p] as const,
  project: (id: number) => ['project', id] as const,
  tasks: (p: Record<string, unknown>) => ['tasks', p] as const,
  activity: (p: Record<string, unknown>) => ['activity', p] as const,
  calendar: (p: Record<string, unknown>) => ['calendar', p] as const,
  schedule: (p: Record<string, unknown>) => ['schedule', p] as const,
  search: (q: string) => ['search', q] as const,
  templates: ['templates'] as const,
  holidays: ['holidays'] as const,
  backups: ['backups'] as const,
}

/** Nach jeder Änderung alles neu laden, was abgeleitete Daten zeigt. Einfach und bei dieser Datenmenge schnell. */
export function useInvalidateAll() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries()
}

export const useMeta = () => useQuery({ queryKey: keys.meta, queryFn: () => api.get<Meta>('/api/meta'), staleTime: 60_000 })
export const useDashboard = () => useQuery({ queryKey: keys.dashboard, queryFn: () => api.get<Dashboard>('/api/dashboard') })
export const useNotifications = () => useQuery({ queryKey: keys.notifications, queryFn: () => api.get<Notification[]>('/api/notifications') })
export const useProjects = (p: Record<string, string | number | boolean | null | undefined> = {}) =>
  useQuery({ queryKey: keys.projects(p), queryFn: () => api.get<Project[]>('/api/projects' + qs(p)) })
export const useProject = (id: number | null) =>
  useQuery({ queryKey: keys.project(id ?? 0), queryFn: () => api.get<ProjectDetail>(`/api/projects/${id}`), enabled: !!id })
export const useTasks = (p: Record<string, string | number | boolean | null | undefined> = {}) =>
  useQuery({ queryKey: keys.tasks(p), queryFn: () => api.get<Task[]>('/api/tasks' + qs(p)) })
export const useActivity = (p: Record<string, string | number | boolean | null | undefined> = {}) =>
  useQuery({ queryKey: keys.activity(p), queryFn: () => api.get<Activity[]>('/api/activity' + qs(p)) })
export const useCalendar = (start: string, end: string, p: Record<string, string | number | boolean | null | undefined> = {}) =>
  useQuery({ queryKey: keys.calendar({ start, end, ...p }), queryFn: () => api.get<CalendarDay[]>('/api/calendar' + qs({ start, end, ...p })) })
export const useSchedule = (p: Record<string, string | number | boolean | null | undefined> = {}) =>
  useQuery({ queryKey: keys.schedule(p), queryFn: () => api.get<Schedule>('/api/schedule' + qs(p)) })
export const useSearch = (q: string) =>
  useQuery({ queryKey: keys.search(q), queryFn: () => api.get<SearchResult>('/api/search' + qs({ q })), enabled: q.trim().length >= 2 })
export const useTemplates = () => useQuery({ queryKey: keys.templates, queryFn: () => api.get<Template[]>('/api/templates') })
export const useTemplatePreview = (id: number | null, deadline: string | null) =>
  useQuery({ queryKey: ['tpl-preview', id, deadline], queryFn: () => api.get<TemplatePreviewRow[]>(`/api/templates/${id}/preview` + qs({ deadline })), enabled: !!id })
export const useHolidays = () => useQuery({ queryKey: keys.holidays, queryFn: () => api.get<Holiday[]>('/api/holidays') })
export const useBackups = () => useQuery({ queryKey: keys.backups, queryFn: () => api.get<Backup[]>('/api/backups') })

function useMut<TArgs, TOut>(fn: (a: TArgs) => Promise<TOut>, onDone?: (out: TOut) => void) {
  const invalidate = useInvalidateAll()
  return useMutation({ mutationFn: fn, onSuccess: (out) => { invalidate(); onDone?.(out) } })
}

export const useCompleteTask = () => useMut((id: number) => api.post<Task>(`/api/tasks/${id}/complete`))
export const useReopenTask = () => useMut((id: number) => api.post<Task>(`/api/tasks/${id}/reopen`))
export const useShiftTask = () => useMut(({ id, workdays }: { id: number; workdays: number }) => api.post<Task>(`/api/tasks/${id}/shift?workdays=${workdays}`))
export const useUpdateTask = () => useMut(({ id, data }: { id: number; data: Record<string, unknown> }) => api.put<Task>(`/api/tasks/${id}`, data))
export const useCreateTask = () => useMut((data: Record<string, unknown>) => api.post<Task>('/api/tasks', data))
export const useDeleteTask = () => useMut((id: number) => api.del(`/api/tasks/${id}`))
export const useReorderTasks = () => useMut(({ projectId, ids }: { projectId: number; ids: number[] }) => api.put<Task[]>(`/api/projects/${projectId}/tasks/order`, { task_ids: ids }))

export const useCreateProject = () => useMut((data: Record<string, unknown>) => api.post<ProjectDetail>('/api/projects', data))
export const useUpdateProject = () => useMut(({ id, data }: { id: number; data: Record<string, unknown> }) => api.put<ProjectDetail>(`/api/projects/${id}`, data))
export const useDeleteProject = () => useMut((id: number) => api.del(`/api/projects/${id}`))
export const useCompleteProject = () => useMut(({ id, open_tasks }: { id: number; open_tasks: string }) => api.post<ProjectDetail>(`/api/projects/${id}/complete`, { open_tasks }))
export const useApplyTemplate = () => useMut(({ id, data }: { id: number; data: Record<string, unknown> }) => api.post<ProjectDetail>(`/api/projects/${id}/apply-template`, data))
export const useFolderLookup = (project_number: string, status: string, name: string) =>
  useQuery({ queryKey: ['folder-lookup', project_number, status, name], enabled: /^\d{2}-\d{3}$/.test(project_number.trim()),
    queryFn: () => api.get<{ expected: string | null; found: string | null }>('/api/projects/folder-lookup' + qs({ project_number: project_number.trim(), status, name })) })
export const useOpenFolder = () => useMutation({ mutationFn: (id: number) => api.post<{ opened: boolean; path: string; message?: string }>(`/api/projects/${id}/open-folder`) })

export const useCreateNote = () => useMut((data: Record<string, unknown>) => api.post<Note>('/api/notes', data))
export const useDeleteNote = () => useMut((id: number) => api.del(`/api/notes/${id}`))

export const useSaveTemplate = () => useMut(({ id, data }: { id?: number; data: Record<string, unknown> }) => id ? api.put<Template>(`/api/templates/${id}`, data) : api.post<Template>('/api/templates', data))
export const useDeleteTemplate = () => useMut((id: number) => api.del(`/api/templates/${id}`))
export const useSaveUser = () => useMut(({ id, data }: { id?: number; data: Record<string, unknown> }) => id ? api.put<User>(`/api/users/${id}`, data) : api.post<User>('/api/users', data))
export const useDeleteUser = () => useMut((id: number) => api.del(`/api/users/${id}`))
export const useSaveTaskType = () => useMut(({ id, data }: { id?: number; data: Record<string, unknown> }) => id ? api.put<TaskType>(`/api/task-types/${id}`, data) : api.post<TaskType>('/api/task-types', data))
export const useDeleteTaskType = () => useMut((id: number) => api.del(`/api/task-types/${id}`))
export const useAddHoliday = () => useMut((data: { date: string; name: string }) => api.post<Holiday>('/api/holidays', data))
export const useDeleteHoliday = () => useMut((id: number) => api.del(`/api/holidays/${id}`))
export const useSaveSettings = () => useMut((data: Record<string, unknown>) => api.put<Settings>('/api/settings', data))
export const useCreateBackup = () => useMut(() => api.post<Backup>('/api/backups'))
