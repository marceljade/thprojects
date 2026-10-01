import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import type { Task } from '@/api/types'
import { useMeta, useTasks } from '@/api/hooks'
import { PageHeader, useUi } from '@/components/layout/Shell'
import { TaskRow } from '@/components/tasks/TaskRow'
import { EmptyState, Segmented, Select, Spinner } from '@/components/ui'
import { CATEGORY, DUE, PRIORITY } from '@/lib/format'

type Bucket = 'alle' | 'ueberfaellig' | 'heute' | 'this_week' | 'next_week' | 'spaeter' | 'ohne_frist' | 'erledigt'

export default function Tasks() {
  const [sp, setSp] = useSearchParams()
  const meta = useMeta().data
  const ui = useUi()
  const bucket = (sp.get('bucket') as Bucket) || 'alle'
  const who = sp.get('who') ?? 'mine'
  const status = sp.get('status') ?? ''
  const project = sp.get('project') ?? ''
  const priority = sp.get('priority') ?? ''
  const ttype = sp.get('type') ?? ''
  const category = sp.get('category') ?? ''
  const setP = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); setSp(n, { replace: true }) }

  const params = {
    mine: who === 'mine', assignee_id: who !== 'mine' && who !== 'alle' ? Number(who) : undefined,
    status: bucket === 'erledigt' ? 'erledigt' : status || undefined, open_only: bucket !== 'erledigt',
    priority: priority || undefined, task_type_id: ttype ? Number(ttype) : undefined, category: category || undefined,
    project_id: project ? Number(project) : undefined,
  }
  const q = useTasks(params)
  const all = q.data ?? []

  const counts = useMemo(() => ({
    alle: all.filter((t) => t.is_open).length,
    ueberfaellig: all.filter((t) => t.due_state === 'ueberfaellig').length,
    heute: all.filter((t) => t.due_state === 'heute').length,
    this_week: all.filter((t) => t.due_state === 'heute' || t.due_state === 'demnaechst' || t.due_state === 'woche').length,
    spaeter: all.filter((t) => t.due_state === 'spaeter').length,
    ohne_frist: all.filter((t) => t.due_state === 'ohne_frist').length,
  }), [all])

  const list = all.filter((t) => {
    if (bucket === 'alle' || bucket === 'erledigt') return true
    if (bucket === 'this_week') return ['heute', 'demnaechst', 'woche'].includes(t.due_state)
    if (bucket === 'next_week') return t.due_state === 'spaeter' || t.due_state === 'woche'
    return t.due_state === bucket
  })

  // Gruppen nach Fälligkeit, in der gewünschten Reihenfolge
  const groups: Array<[string, Task[]]> = []
  for (const key of ['ueberfaellig', 'heute', 'demnaechst', 'woche', 'spaeter', 'ohne_frist', 'erledigt'] as const) {
    const g = list.filter((t) => t.due_state === key)
    if (g.length) groups.push([DUE[key], g])
  }
  const projects = [...new Map(all.map((t) => [t.project_id, t])).values()].sort((a, b) => a.project_number.localeCompare(b.project_number))

  return (
    <div className="page">
      <PageHeader title={who === 'mine' ? 'Meine Aufgaben' : 'Aufgaben'} sub={`${list.length} Aufgaben`}>
        <button className="btn-primary" onClick={() => ui.newTask()}><Plus size={14} />Aufgabe</button>
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <Segmented value={bucket} onChange={(v) => setP('bucket', v === 'alle' ? '' : v)} options={[
          { value: 'alle', label: 'Offen', count: counts.alle }, { value: 'ueberfaellig', label: 'Überfällig', count: counts.ueberfaellig },
          { value: 'heute', label: 'Heute', count: counts.heute }, { value: 'this_week', label: 'Diese Woche', count: counts.this_week },
          { value: 'spaeter', label: 'Später', count: counts.spaeter }, { value: 'ohne_frist', label: 'Ohne Frist', count: counts.ohne_frist },
          { value: 'erledigt', label: 'Erledigt' },
        ]} />
      </div>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Select className="w-auto h-8 text-[12.5px]" value={who} onChange={(v) => setP('who', v === 'mine' ? '' : v)}
          options={[{ value: 'mine', label: `Meine (${meta?.settings.my_user_code ?? '–'})` }, { value: 'alle', label: 'Alle Bearbeiter' }, ...(meta?.users ?? []).filter((u) => u.active && u.id !== meta?.settings.my_user_id).map((u) => ({ value: String(u.id), label: u.code }))]} />
        <Select className="w-auto h-8 text-[12.5px]" value={project} onChange={(v) => setP('project', v)} placeholder="Alle Projekte" options={projects.map((t) => ({ value: t.project_id, label: `${t.project_number} · ${t.project_name}` }))} />
        <Select className="w-auto h-8 text-[12.5px]" value={category} onChange={(v) => setP('category', v)} placeholder="Alle Kategorien" options={Object.entries(CATEGORY).map(([value, label]) => ({ value, label }))} />
        {bucket !== 'erledigt' && <Select className="w-auto h-8 text-[12.5px]" value={status} onChange={(v) => setP('status', v)} placeholder="Jeder Status" options={(meta?.task_statuses ?? []).filter((s) => s.open).map((s) => ({ value: s.value, label: s.label }))} />}
        <Select className="w-auto h-8 text-[12.5px]" value={priority} onChange={(v) => setP('priority', v)} placeholder="Jede Priorität" options={Object.entries(PRIORITY).map(([value, label]) => ({ value, label }))} />
        <Select className="w-auto h-8 text-[12.5px]" value={ttype} onChange={(v) => setP('type', v)} placeholder="Jede Aufgabenart" options={(meta?.task_types ?? []).map((x) => ({ value: x.id, label: x.name }))} />
        {(status || project || priority || ttype || category || who !== 'mine') && <button className="btn-ghost btn-sm" onClick={() => setSp(new URLSearchParams(bucket !== 'alle' ? { bucket } : {}), { replace: true })}>Filter zurücksetzen</button>}
      </div>

      {q.isLoading ? <Spinner /> : list.length === 0 ? (
        <EmptyState title="Keine Aufgaben in dieser Auswahl" text={who === 'mine' ? 'Aufgaben erscheinen hier, sobald sie dir zugewiesen sind.' : undefined}
          action={<button className="btn-outline" onClick={() => ui.newTask()}><Plus size={14} />Aufgabe anlegen</button>} />
      ) : (
        <div className="card divide-y">
          {groups.map(([label, g]) => (
            <div key={label} className="py-1">
              <div className="px-4 pt-2 pb-1 text-[12px] text-muted">{label} <span className="text-faint">{g.length}</span></div>
              <div className="px-1.5">{g.map((t) => <TaskRow key={t.id} t={t} onOpen={ui.openTask} />)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
