import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { useProjects } from '@/api/hooks'
import { PageHeader, useUi } from '@/components/layout/Shell'
import { Dot, EmptyState, ProgressBar, RoundChip, Segmented, Spinner } from '@/components/ui'
import { CATEGORY, CATEGORY_SHORT, cx, fmtDate, PRIORITY, PROJECT_STATUS, relDays, signalBg, SIGNAL } from '@/lib/format'
import type { Category } from '@/api/types'

const FILTERS = [
  { value: 'aktiv', label: 'Aktiv' }, { value: 'kritisch', label: 'Kritisch' }, { value: 'anfrage', label: 'Anfrage' }, { value: 'angebot', label: 'Angebot' },
  { value: 'beauftragt', label: 'Beauftragt' }, { value: 'in_bearbeitung', label: 'In Bearbeitung' }, { value: 'wartet_kunde', label: 'Wartet auf Kunde' },
  { value: 'abgeschlossen', label: 'Abgeschlossen' }, { value: 'alle', label: 'Alle' },
]

export default function Projects() {
  const [sp, setSp] = useSearchParams()
  const filter = sp.get('filter') ?? 'aktiv'
  const category = (sp.get('category') ?? '') as Category | ''
  const [q, setQ] = useState('')
  const ui = useUi()
  const params: Record<string, string | boolean | undefined> = { q: q || undefined, category: category || undefined }
  if (filter === 'aktiv') params.active = true
  else if (filter === 'kritisch') { params.active = true; params.signal = 'rot,gelb' }
  else if (filter !== 'alle') params.status = filter
  const list = useProjects(params)
  const all = useProjects({})
  const setP = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); setSp(n, { replace: true }) }
  const catCounts = Object.fromEntries((Object.keys(CATEGORY) as Category[]).map((c) => [c, (all.data ?? []).filter((p) => p.category === c && (filter !== 'aktiv' || p.is_active)).length]))

  return (
    <div className="page">
      <PageHeader title="Projekte" sub={`${list.data?.length ?? 0} Projekte`}>
        <button className="btn-primary" onClick={ui.newProject}><Plus size={14} />Projekt</button>
      </PageHeader>
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Segmented value={filter} onChange={(v) => setP('filter', v === 'aktiv' ? '' : v)} options={FILTERS} />
        <span className="w-px h-5 bg-line hidden sm:block" />
        <Segmented value={category || 'alle'} onChange={(v) => setP('category', v === 'alle' ? '' : v)}
          options={[{ value: 'alle', label: 'Alle Arten' }, ...(Object.keys(CATEGORY) as Category[]).map((c) => ({ value: c, label: CATEGORY[c], count: catCounts[c] }))]} />
        <div className="relative ml-auto">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
          <input className="input h-8 pl-8 w-64" placeholder="Projekt suchen …" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      {list.isLoading ? <Spinner /> : (list.data ?? []).length === 0 ? (
        <EmptyState title="Keine Projekte in dieser Auswahl" action={<button className="btn-outline" onClick={ui.newProject}><Plus size={14} />Projekt anlegen</button>} />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[12px] text-muted border-b">
                <th className="font-medium px-4 py-2.5 w-8"></th>
                <th className="font-medium px-2 py-2.5">Projekt</th>
                <th className="font-medium px-2 py-2.5 hidden md:table-cell">Art</th>
                <th className="font-medium px-2 py-2.5 hidden lg:table-cell">Auftraggeber</th>
                <th className="font-medium px-2 py-2.5">Leitung</th>
                <th className="font-medium px-2 py-2.5">Status</th>
                <th className="font-medium px-2 py-2.5 w-36">Fortschritt</th>
                <th className="font-medium px-2 py-2.5 hidden xl:table-cell">Nächste Aufgabe</th>
                <th className="font-medium px-2 py-2.5">Nächste Frist</th>
                <th className="font-medium px-4 py-2.5">Projektfrist</th>
              </tr>
            </thead>
            <tbody>
              {(list.data ?? []).map((p) => (
                <tr key={p.id} className="border-b last:border-0 row-hover">
                  <td className="px-4 py-2.5"><span title={`${SIGNAL[p.signal]}${p.reasons.length ? ': ' + p.reasons.join(', ') : ''}`}><Dot className={signalBg(p.signal)} size={9} /></span></td>
                  <td className="px-2 py-2.5">
                    <Link to={`/projekte/${p.id}`} className="block hover:text-accent">
                      <div className="font-medium">{p.project_number}{p.priority !== 'normal' && <span className={cx('ml-2 text-[11px] font-normal', p.priority === 'kritisch' ? 'text-rot' : p.priority === 'hoch' ? 'text-orange' : 'text-faint')}>{PRIORITY[p.priority]}</span>}</div>
                      <div className="text-muted truncate max-w-[320px] flex items-center gap-2"><span className="truncate">{p.name}</span><RoundChip n={p.round_number} title={p.round_title} /></div>
                    </Link>
                  </td>
                  <td className="px-2 py-2.5 hidden md:table-cell text-muted">{CATEGORY_SHORT[p.category]}</td>
                  <td className="px-2 py-2.5 hidden lg:table-cell text-muted truncate max-w-[180px]">{p.client || '–'}</td>
                  <td className="px-2 py-2.5">{p.assignee_code ?? <span className="text-rot">–</span>}</td>
                  <td className="px-2 py-2.5 text-muted whitespace-nowrap">{PROJECT_STATUS[p.status]}</td>
                  <td className="px-2 py-2.5"><ProgressBar value={p.progress} /></td>
                  <td className="px-2 py-2.5 hidden xl:table-cell text-muted truncate max-w-[220px]">{p.next_task_title ?? (p.is_active ? <span className="text-gelb">keine offene Aufgabe</span> : '–')}</td>
                  <td className="px-2 py-2.5 whitespace-nowrap">{p.next_due ? <><span className={p.overdue_count ? 'text-rot' : ''}>{fmtDate(p.next_due, { year: false })}</span><span className="text-faint text-[12px]"> {relDays(p.next_due)}</span></> : <span className="text-faint">–</span>}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap">{p.deadline ? <><span className={p.remaining_workdays !== null && p.remaining_workdays < 0 ? 'text-rot' : ''}>{fmtDate(p.deadline, { year: false })}</span>{p.deadline_kw && <span className="text-faint text-[12px]"> KW {p.deadline_kw}</span>}</> : <span className="text-faint">–</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
