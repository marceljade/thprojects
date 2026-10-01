import { Link } from 'react-router-dom'
import { AlertTriangle, Clock } from 'lucide-react'
import type { Task } from '@/api/types'
import { useCompleteTask, useReopenTask } from '@/api/hooks'
import { useToast, CheckCircle } from '@/components/ui'
import { cx, dueColor, dueLabel, fmtDate, PRIORITY, TASK_STATUS } from '@/lib/format'

export function PriorityMark({ p }: { p: Task['priority'] }) {
  if (p === 'normal') return null
  const cls = p === 'kritisch' ? 'text-rot border-rot/40' : p === 'hoch' ? 'text-orange border-orange/40' : 'text-faint border-line'
  return <span className={cx('text-[11px] px-1.5 h-5 inline-flex items-center rounded border', cls)}>{PRIORITY[p]}</span>
}

export function TaskRow({ t, onOpen, showProject = true, dense = false, railLevel }:
  { t: Task; onOpen: (t: Task) => void; showProject?: boolean; dense?: boolean; railLevel?: string }) {
  const complete = useCompleteTask()
  const reopen = useReopenTask()
  const toast = useToast()
  const done = t.status === 'erledigt'
  const toggle = () => {
    if (done) reopen.mutate(t.id, { onSuccess: () => toast('Aufgabe wieder geöffnet') })
    else complete.mutate(t.id, { onSuccess: () => toast(`„${t.title}“ erledigt`) })
  }
  const rail = railLevel ?? (t.due_state === 'ueberfaellig' ? 'rot' : t.due_state === 'heute' ? 'orange' : t.due_state === 'demnaechst' ? 'gelb' : t.status === 'wartet' ? 'blau' : '')
  return (
    <div className={cx('relative flex items-center gap-3 pl-4 pr-3 rounded-md row-hover cursor-pointer group', dense ? 'py-1.5' : 'py-2')} onClick={() => onOpen(t)}>
      {rail && <span className={cx('rail', { rot: 'bg-rot', orange: 'bg-orange', gelb: 'bg-gelb', blau: 'bg-blau' }[rail])} />}
      <CheckCircle checked={done} onChange={toggle} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 min-w-0">
          <span className={cx('truncate', done ? 'text-faint line-through' : 'text-ink font-medium')}>{t.title}</span>
          <PriorityMark p={t.priority} />
          {t.predecessor_open && ['ueberfaellig', 'heute', 'demnaechst', 'woche'].includes(t.due_state) && <span title="Vorgängeraufgabe ist noch offen" className="text-gelb inline-flex"><AlertTriangle size={13} /></span>}
          {t.status === 'wartet' && <span className="text-[11px] text-blau inline-flex items-center gap-1"><Clock size={12} />wartet{t.waiting_on ? ` auf ${t.waiting_on}` : ''}</span>}
        </div>
        {showProject && (
          <div className="text-[12px] text-muted truncate mt-0.5">
            <Link to={`/projekte/${t.project_id}`} onClick={(e) => e.stopPropagation()} className="hover:text-accent">{t.project_number}</Link>
            <span className="mx-1">·</span>{t.project_name}
            {!done && t.status !== 'nicht_begonnen' && t.status !== 'wartet' && <><span className="mx-1">·</span>{TASK_STATUS[t.status]}</>}
          </div>
        )}
      </div>
      <div className="text-right shrink-0 hidden sm:block">
        <div className={cx('text-[12.5px]', dueColor(t.due_state))}>{dueLabel(t)}</div>
        {t.due_date && <div className="text-[11px] text-faint">{fmtDate(t.due_date)}{t.kw ? ` · KW ${t.kw}` : ''}</div>}
      </div>
      {t.assignee_code && <span className="shrink-0 w-9 h-6 rounded bg-raised border text-[11px] text-muted flex items-center justify-center" title="Bearbeiter">{t.assignee_code}</span>}
    </div>
  )
}
