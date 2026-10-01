import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CalendarPlus, Check, FolderOpen, RotateCcw, Trash2 } from 'lucide-react'
import type { Task } from '@/api/types'
import { api } from '@/api/client'
import { useCompleteTask, useCreateNote, useDeleteTask, useMeta, useReopenTask, useShiftTask, useUpdateTask } from '@/api/hooks'
import { Confirm, DateInput, Dialog, Field, Select, useToast } from '@/components/ui'
import { cx, dueColor, dueLabel, fmtDate, fmtDateTime, PRIORITY, TASK_STATUS } from '@/lib/format'
import type { Note } from '@/api/types'
import { useQuery } from '@tanstack/react-query'

/** Aufgabe ansehen und bearbeiten. Alle Felder sind direkt editierbar, Speichern je Feld beim Verlassen. */
export function TaskDialog({ task, onClose }: { task: Task | null; onClose: () => void }) {
  const meta = useMeta().data
  const update = useUpdateTask()
  const complete = useCompleteTask()
  const reopen = useReopenTask()
  const shift = useShiftTask()
  const del = useDeleteTask()
  const addNote = useCreateNote()
  const toast = useToast()
  const nav = useNavigate()
  const [form, setForm] = useState<Partial<Task>>({})
  const [note, setNote] = useState('')
  const [confirm, setConfirm] = useState(false)
  const notes = useQuery({ queryKey: ['task-notes', task?.id], queryFn: () => api.get<Note[]>(`/api/tasks/${task!.id}/notes`), enabled: !!task })

  useEffect(() => { if (task) setForm(task) }, [task])
  if (!task) return null
  const t = task
  const set = (k: keyof Task, v: unknown) => setForm((f) => ({ ...f, [k]: v }))

  const save = (patch: Record<string, unknown>) => {
    const clear = Object.entries(patch).filter(([, v]) => v === null || v === '').map(([k]) => k)
    const data: Record<string, unknown> = { ...Object.fromEntries(Object.entries(patch).filter(([, v]) => v !== null && v !== '')) }
    const clearable = ['due_date', 'start_date', 'reminder_date', 'waiting_since', 'predecessor_id', 'assignee_id', 'task_type_id']
    data.clear = clear.filter((k) => clearable.includes(k))
    for (const k of clear) if (!clearable.includes(k)) data[k] = ''
    update.mutate({ id: t.id, data }, { onError: (e) => toast(e.message, 'error') })
  }
  const blurSave = (k: keyof Task) => () => { if (form[k] !== t[k]) save({ [k]: form[k] }) }

  const users = (meta?.users ?? []).filter((u) => u.active || u.id === t.assignee_id).map((u) => ({ value: u.id, label: u.name ? `${u.code} – ${u.name}` : u.code }))
  const done = t.status === 'erledigt'

  return (
    <Dialog open={!!task} onClose={onClose} title={`${t.project_number} · Aufgabe`} width="max-w-2xl">
      <div className="flex items-start gap-3">
        <input className="flex-1 text-[17px] font-semibold bg-transparent border-b border-transparent hover:border-line focus:border-accent outline-none py-1 -ml-0.5"
          value={form.title ?? ''} onChange={(e) => set('title', e.target.value)} onBlur={blurSave('title')} />
      </div>
      <div className={cx('mt-1 text-[13px]', dueColor(t.due_state))}>{dueLabel(t)}{t.kw ? ` · KW ${t.kw}` : ''}</div>

      <div className="mt-4 flex flex-wrap gap-2">
        {done ? (
          <button className="btn-outline" onClick={() => reopen.mutate(t.id, { onSuccess: () => toast('Wieder geöffnet') })}><RotateCcw size={14} />Wieder öffnen</button>
        ) : (
          <button className="btn-primary" onClick={() => complete.mutate(t.id, { onSuccess: () => { toast('Erledigt'); onClose() } })}><Check size={14} />Erledigt</button>
        )}
        {!done && [1, 3, 5].map((n) => (
          <button key={n} className="btn-outline" title={`Frist um ${n} Arbeitstage verschieben`} onClick={() => shift.mutate({ id: t.id, workdays: n }, { onSuccess: () => toast(`Frist um ${n} Arbeitstage verschoben`) })}>
            <CalendarPlus size={14} />+{n} AT
          </button>
        ))}
        <button className="btn-outline" onClick={() => { onClose(); nav(`/projekte/${t.project_id}`) }}><FolderOpen size={14} />Projekt öffnen</button>
        <button className="btn-ghost text-rot ml-auto" onClick={() => setConfirm(true)}><Trash2 size={14} />Löschen</button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-5">
        <Field label="Status">
          <Select value={form.status} onChange={(v) => { set('status', v); save({ status: v }) }} options={(meta?.task_statuses ?? []).map((o) => ({ value: o.value, label: o.label }))} />
        </Field>
        <Field label="Priorität">
          <Select value={form.priority} onChange={(v) => { set('priority', v); save({ priority: v }) }} options={Object.entries(PRIORITY).map(([value, label]) => ({ value, label }))} />
        </Field>
        <Field label="Bearbeiter">
          <Select value={form.assignee_id ?? ''} onChange={(v) => { set('assignee_id', v ? Number(v) : null); save({ assignee_id: v ? Number(v) : null }) }} options={users} placeholder="–" />
        </Field>
        <Field label="Start">
          <DateInput value={form.start_date} onChange={(v) => set('start_date', v || null)} onBlur={blurSave('start_date')} />
        </Field>
        <Field label="Frist">
          <DateInput value={form.due_date} onChange={(v) => set('due_date', v || null)} onBlur={blurSave('due_date')} />
        </Field>
        <Field label="Aufgabenart">
          <Select value={form.task_type_id ?? ''} onChange={(v) => { set('task_type_id', v ? Number(v) : null); save({ task_type_id: v ? Number(v) : null }) }}
            options={(meta?.task_types ?? []).map((x) => ({ value: x.id, label: x.name }))} placeholder="–" />
        </Field>
        <Field label="Fortschritt %">
          <input type="number" min={0} max={100} className="input" value={form.progress ?? 0} onChange={(e) => set('progress', Number(e.target.value))} onBlur={blurSave('progress')} disabled={done} />
        </Field>
        <Field label="Gewicht" hint="für den Projektfortschritt">
          <input type="number" min={0} step={0.5} className="input" value={form.weight ?? 1} onChange={(e) => set('weight', Number(e.target.value))} onBlur={blurSave('weight')} />
        </Field>
        <Field label="Vorgänger (ID)">
          <input type="number" className="input" value={form.predecessor_id ?? ''} onChange={(e) => set('predecessor_id', e.target.value ? Number(e.target.value) : null)} onBlur={blurSave('predecessor_id')} />
        </Field>
      </div>

      {form.status === 'wartet' && (
        <div className="mt-3 p-3 rounded-md border border-blau/30 bg-blau/5 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Field label="Worauf wird gewartet?" className="col-span-2"><input className="input" value={form.waiting_for ?? ''} onChange={(e) => set('waiting_for', e.target.value)} onBlur={blurSave('waiting_for')} placeholder="z. B. Unterlagen" /></Field>
          <Field label="Von wem?"><input className="input" value={form.waiting_on ?? ''} onChange={(e) => set('waiting_on', e.target.value)} onBlur={blurSave('waiting_on')} placeholder="Kunde, Kollege" /></Field>
          <Field label="Erinnerung am"><DateInput value={form.reminder_date} onChange={(v) => set('reminder_date', v || null)} onBlur={blurSave('reminder_date')} /></Field>
          <div className="col-span-full text-[12px] text-muted">wartet seit {fmtDate(t.waiting_since)}</div>
        </div>
      )}

      <Field label="Beschreibung" className="mt-3">
        <textarea className="input-area" value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} onBlur={blurSave('description')} placeholder="Was genau ist zu tun?" />
      </Field>

      <div className="mt-4 border-t pt-3">
        <div className="flex gap-2">
          <input className="input" placeholder="Notiz zu dieser Aufgabe …" value={note} onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && note.trim()) { addNote.mutate({ project_id: t.project_id, task_id: t.id, content: note }, { onSuccess: () => { setNote(''); notes.refetch(); toast('Notiz gespeichert') } }) } }} />
          <button className="btn-outline" disabled={!note.trim()} onClick={() => addNote.mutate({ project_id: t.project_id, task_id: t.id, content: note }, { onSuccess: () => { setNote(''); notes.refetch(); toast('Notiz gespeichert') } })}>Speichern</button>
        </div>
        <ul className="mt-2 space-y-2">
          {(notes.data ?? []).map((n) => (
            <li key={n.id} className="text-[13px]"><span className="text-faint">{fmtDateTime(n.created_at)} · {n.author_code}</span><div className="whitespace-pre-wrap">{n.content}</div></li>
          ))}
        </ul>
      </div>
      <div className="mt-3 text-[11px] text-faint">Angelegt {fmtDate(t.created_at)} · geändert {fmtDate(t.updated_at)}{t.completed_at ? ` · erledigt ${fmtDate(t.completed_at)}` : ''} · Status {TASK_STATUS[t.status]}</div>

      <Confirm open={confirm} onClose={() => setConfirm(false)} title="Aufgabe löschen?" text={`„${t.title}“ wird endgültig gelöscht. Notizen dazu bleiben beim Projekt erhalten.`}
        onConfirm={() => del.mutate(t.id, { onSuccess: () => { toast('Aufgabe gelöscht'); onClose() } })} />
    </Dialog>
  )
}
