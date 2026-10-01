import { Link } from 'react-router-dom'
import { useActivity } from '@/api/hooks'
import { PageHeader } from '@/components/layout/Shell'
import { EmptyState, Spinner } from '@/components/ui'
import { fmtDate, fmtDateTime, parseDate } from '@/lib/format'

export default function ActivityPage() {
  const q = useActivity({ limit: 300 })
  const list = q.data ?? []
  const groups = new Map<string, typeof list>()
  for (const a of list) { const d = a.created_at.slice(0, 10); groups.set(d, [...(groups.get(d) ?? []), a]) }
  return (
    <div className="page">
      <PageHeader title="Aktivitäten" sub="Was zuletzt passiert ist – Anlegen, Erledigen, Fristen, Status, Notizen" />
      {q.isLoading ? <Spinner /> : list.length === 0 ? <EmptyState title="Noch keine Aktivitäten" /> : (
        <div className="space-y-4">
          {[...groups.entries()].map(([day, items]) => (
            <section key={day} className="card">
              <header className="px-4 py-2 border-b text-[12px] text-muted">{fmtDate(day, { weekday: true })}{parseDate(day)!.toDateString() === new Date().toDateString() ? ' · heute' : ''}</header>
              <ul className="divide-y">
                {items.map((a) => (
                  <li key={a.id} className="px-4 py-2 text-[13px] flex gap-3">
                    <span className="text-faint shrink-0 w-12">{fmtDateTime(a.created_at).slice(11)}</span>
                    <span className="text-muted shrink-0 w-10">{a.user_code ?? '–'}</span>
                    <span className="min-w-0">
                      {a.project_id && <Link to={`/projekte/${a.project_id}`} className="font-medium hover:text-accent mr-1.5">{a.project_number}</Link>}
                      {a.action}{a.task_title ? <span className="text-muted"> · {a.task_title}</span> : ''}
                      {a.field && !['aufgabe', 'notiz', 'vorlage'].includes(a.field) && <span className="text-muted"> · {a.field}{a.old_value ? `: ${a.old_value} →` : ':'} {a.new_value || '–'}</span>}
                      {['aufgabe', 'notiz', 'vorlage'].includes(a.field) && a.new_value && <span className="text-muted"> · {a.new_value}</span>}
                      {a.details && <span className="text-faint"> · {a.details}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
