import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '@/api/client'
import { useSchedule } from '@/api/hooks'
import type { Task } from '@/api/types'
import { PageHeader, useUi } from '@/components/layout/Shell'
import { Gantt } from '@/components/schedule/Gantt'
import { Segmented, Spinner } from '@/components/ui'
import { addDays, CATEGORY, toIso, weekStart } from '@/lib/format'
import type { Category } from '@/api/types'

export default function Schedule() {
  const [offset, setOffset] = useState(0)
  const [weeks, setWeeks] = useState(10)
  const [category, setCategory] = useState<Category | 'alle'>('alle')
  const [withDone, setWithDone] = useState(false)
  const ui = useUi()
  const start = addDays(weekStart(new Date()), 7 * (offset - 1))
  const end = addDays(start, 7 * weeks - 1)
  const q = useSchedule({ start: toIso(start), end: toIso(end), category: category === 'alle' ? undefined : category, include_done: withDone })

  return (
    <div className="page">
      <PageHeader title="Zeitplan" sub="Alle aktiven Projekte, eine Zeile je Aufgabe mit Datum. Balken von Start bis Frist, ohne Start zwei Arbeitstage vor der Frist.">
        <Segmented value={category} onChange={setCategory} options={[{ value: 'alle', label: 'Alle Arten' }, ...(Object.keys(CATEGORY) as Category[]).map((c) => ({ value: c, label: CATEGORY[c] }))]} />
        <Segmented value={String(weeks)} onChange={(v) => setWeeks(Number(v))} options={[{ value: '6', label: '6 Wochen' }, { value: '10', label: '10 Wochen' }, { value: '16', label: '16 Wochen' }]} />
        <label className="text-[12px] text-muted flex items-center gap-1.5"><input type="checkbox" checked={withDone} onChange={(e) => setWithDone(e.target.checked)} />erledigte</label>
      </PageHeader>
      <div className="flex items-center gap-2 mb-3">
        <button className="btn-icon h-8 w-8" onClick={() => setOffset((o) => o - 2)} aria-label="früher"><ChevronLeft size={16} /></button>
        <button className="btn-outline btn-sm" onClick={() => setOffset(0)}>Heute</button>
        <button className="btn-icon h-8 w-8" onClick={() => setOffset((o) => o + 2)} aria-label="später"><ChevronRight size={16} /></button>
        <span className="ml-3 flex items-center gap-3 text-[11.5px] text-muted">
          <span className="inline-flex items-center gap-1"><i className="w-3 h-2 rounded-sm bg-accent" />geplant</span>
          <span className="inline-flex items-center gap-1"><i className="w-3 h-2 rounded-sm bg-orange" />bald fällig</span>
          <span className="inline-flex items-center gap-1"><i className="w-3 h-2 rounded-sm bg-rot" />überfällig</span>
          <span className="inline-flex items-center gap-1"><i className="w-3 h-2 rounded-sm bg-blau" />wartet</span>
          <span className="inline-flex items-center gap-1"><i className="w-3 h-2 rounded-sm bg-gruen/70" />erledigt</span>
          <span className="inline-flex items-center gap-1"><i className="w-0.5 h-3 bg-accent" />heute</span>
          <span className="inline-flex items-center gap-1"><i className="w-0 h-3 border-l-2 border-dashed border-rot/60" />Projektfrist</span>
        </span>
      </div>
      <div className="card">
        {q.isLoading || !q.data ? <Spinner /> : <Gantt data={q.data} onTask={async (id) => ui.openTask(await api.get<Task>(`/api/tasks/${id}`))} />}
      </div>
    </div>
  )
}
