import { useEffect, useState } from 'react'
import { useCreateTask, useMeta, useProjects } from '@/api/hooks'
import { Dialog, Field, Select, useToast } from '@/components/ui'
import { PRIORITY, todayIso } from '@/lib/format'

const empty = { project_id: '', title: '', task_type_id: '', assignee_id: '', status: 'nicht_begonnen', priority: 'normal', start_date: '', due_date: '', description: '', note: '' }

/** Schnell eine Aufgabe anlegen. Enter im Titel reicht, wenn Projekt gewählt ist. */
export function TaskForm({ open, onClose, projectId }: { open: boolean; onClose: () => void; projectId?: number }) {
  const meta = useMeta().data
  const projects = useProjects({ active: true }).data ?? []
  const allProjects = useProjects({}).data ?? []
  const create = useCreateTask()
  const toast = useToast()
  const [f, setF] = useState({ ...empty })
  const [showAll, setShowAll] = useState(false)
  useEffect(() => {
    if (open) setF({ ...empty, project_id: projectId ? String(projectId) : '', assignee_id: meta?.settings.my_user_id ? String(meta.settings.my_user_id) : '' })
  }, [open, projectId, meta])
  const set = (k: keyof typeof empty, v: string) => setF((x) => ({ ...x, [k]: v }))
  const list = showAll || (projectId && !projects.some((p) => p.id === projectId)) ? allProjects : projects

  const submit = () => {
    if (!f.project_id) return toast('Bitte ein Projekt wählen.', 'error')
    if (!f.title.trim()) return toast('Die Aufgabe braucht einen Namen.', 'error')
    const data: Record<string, unknown> = {
      project_id: Number(f.project_id), title: f.title.trim(), status: f.status, priority: f.priority, description: f.description, note: f.note,
      task_type_id: f.task_type_id ? Number(f.task_type_id) : null, assignee_id: f.assignee_id ? Number(f.assignee_id) : null,
      start_date: f.start_date || null, due_date: f.due_date || null,
    }
    create.mutate(data, { onSuccess: () => { toast(`Aufgabe „${f.title.trim()}“ angelegt`); onClose() }, onError: (e) => toast(e.message, 'error') })
  }

  return (
    <Dialog open={open} onClose={onClose} title="Neue Aufgabe" footer={
      <>
        <button className="btn-outline" onClick={onClose}>Abbrechen</button>
        <button className="btn-primary" onClick={submit} disabled={create.isPending}>Aufgabe speichern</button>
      </>
    }>
      <div className="space-y-3">
        <Field label="Projekt" hint={!showAll && !projectId ? <button className="underline" onClick={() => setShowAll(true)}>auch inaktive Projekte zeigen</button> : undefined}>
          <Select value={f.project_id} onChange={(v) => set('project_id', v)} placeholder="Projekt wählen …"
            options={list.map((p) => ({ value: p.id, label: `${p.project_number} · ${p.name}` }))} />
        </Field>
        <Field label="Aufgabe">
          <input className="input" autoFocus value={f.title} onChange={(e) => set('title', e.target.value)} placeholder="z. B. Messdaten auswerten"
            onKeyDown={(e) => { if (e.key === 'Enter') submit() }} />
        </Field>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Field label="Bearbeiter">
            <Select value={f.assignee_id} onChange={(v) => set('assignee_id', v)} placeholder="–" options={(meta?.users ?? []).filter((u) => u.active).map((u) => ({ value: u.id, label: u.code }))} />
          </Field>
          <Field label="Status">
            <Select value={f.status} onChange={(v) => set('status', v)} options={(meta?.task_statuses ?? []).map((o) => ({ value: o.value, label: o.label }))} />
          </Field>
          <Field label="Priorität">
            <Select value={f.priority} onChange={(v) => set('priority', v)} options={Object.entries(PRIORITY).map(([value, label]) => ({ value, label }))} />
          </Field>
          <Field label="Aufgabenart">
            <Select value={f.task_type_id} onChange={(v) => set('task_type_id', v)} placeholder="–" options={(meta?.task_types ?? []).filter((x) => x.active).map((x) => ({ value: x.id, label: x.name }))} />
          </Field>
          <Field label="Start"><input type="date" className="input" value={f.start_date} onChange={(e) => set('start_date', e.target.value)} /></Field>
          <Field label="Frist">
            <div className="flex gap-1">
              <input type="date" className="input" value={f.due_date} onChange={(e) => set('due_date', e.target.value)} />
              <button type="button" className="btn-outline btn-sm h-9" title="heute" onClick={() => set('due_date', todayIso())}>heute</button>
            </div>
          </Field>
        </div>
        <Field label="Beschreibung"><textarea className="input-area" value={f.description} onChange={(e) => set('description', e.target.value)} /></Field>
        <Field label="Erste Notiz (optional)"><input className="input" value={f.note} onChange={(e) => set('note', e.target.value)} /></Field>
      </div>
    </Dialog>
  )
}
