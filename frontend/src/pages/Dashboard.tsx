import { useLayoutEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Clock } from 'lucide-react'
import type { Project, Task } from '@/api/types'
import { useDashboard } from '@/api/hooks'
import { useUi } from '@/components/layout/Shell'
import { TaskRow } from '@/components/tasks/TaskRow'
import { Dot, ProgressBar, RoundChip, Spinner } from '@/components/ui'
import { cx, fmtDate, fmtLong, relDays, signalBg, weekdayLong, fmtDateTime } from '@/lib/format'

function greeting(name: string): string {
  const h = new Date().getHours()
  const g = h < 11 ? 'Guten Morgen' : h < 17 ? 'Guten Tag' : 'Guten Abend'
  return name ? `${g}, ${name}` : g
}

/* Kachelstreifen: Zahl und Label nebeneinander, Tönung nur bei Wert > 0 und Semantikfarbe */
function Stat({ label, value, to, tone }: { label: string; value: number; to: string; tone?: 'rot' | 'orange' }) {
  const nav = useNavigate()
  const hot = value > 0 && tone
  const cls = hot === 'rot' ? 'bg-rot/[0.07] border-rot/30 text-rot' : hot === 'orange' ? 'bg-orange/[0.08] border-orange/30 text-orange' : 'text-ink'
  return (
    <button onClick={() => nav(to)} className={cx('text-left card h-[40px] px-3 flex items-center gap-2 hover:border-faint transition-colors min-w-0', cls)}>
      <span className="text-[18px] font-semibold leading-none tracking-tight tabular-nums">{value}</span>
      <span className={cx('text-[12px] truncate', hot ? 'opacity-80' : 'text-muted')}>{label}</span>
    </button>
  )
}

/* Bereich: als Karte mit Inhalt, oder als eine Zeile ohne Rahmen, wenn er leer ist */
function Section({ title, count, to, empty, children, className }:
  { title: string; count?: number; to?: string; empty?: string; children?: React.ReactNode; className?: string }) {
  if (empty) {
    return <p className={cx('px-1 py-1 text-[13px] text-muted', className)}><span className="font-medium text-ink">{title}</span> · {empty}</p>
  }
  return (
    <section className={cx('card', className)}>
      <header className="flex items-center justify-between px-4 pt-2 pb-1.5">
        <h2 className="h2 flex items-center gap-2">{title}{count !== undefined && <span className="text-[12px] font-normal text-faint">{count}</span>}</h2>
        {to && <Link to={to} className="text-[12px] text-muted hover:text-accent inline-flex items-center gap-1">alle<ArrowRight size={12} /></Link>}
      </header>
      <div className="px-1.5 pb-1.5">{children}</div>
    </section>
  )
}

const SIGNAL_ORDER: Record<string, number> = { rot: 0, gelb: 1, gruen: 2, grau: 3, fertig: 4 }

function ProjectLine({ p }: { p: Project }) {
  const note = p.signal === 'rot' || p.signal === 'gelb' ? [...p.reasons, ...p.warnings].join(' · ') : ''
  return (
    <Link to={`/projekte/${p.id}`} className="relative block pl-4 pr-2.5 py-1.5 rounded-md row-hover">
      {p.signal === 'rot' && <span className="rail bg-rot" />}
      <div className="flex items-center gap-2.5 min-w-0">
        <Dot className={signalBg(p.signal)} />
        <span className="font-medium shrink-0">{p.project_number}</span>
        <span className="truncate text-muted flex-1">{p.name}</span>
        <RoundChip n={p.round_number} title={p.round_title} />
        <span className="w-28 shrink-0 hidden sm:block"><ProgressBar value={p.progress} /></span>
      </div>
      {note && <div className="text-[12px] text-muted truncate mt-0.5 pl-[18px]">{note}</div>}
    </Link>
  )
}

export default function Dashboard() {
  const q = useDashboard()
  const ui = useUi()
  // „Zuletzt" nur, wenn unter „Wartet auf Rückmeldung" noch Platz im Viewport ist
  const rightRef = useRef<HTMLDivElement>(null)
  const [roomBelow, setRoomBelow] = useState(false)
  useLayoutEffect(() => {
    const measure = () => {
      const el = rightRef.current
      if (!el) return
      setRoomBelow(window.innerHeight - el.getBoundingClientRect().bottom > 160)
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [q.data])

  if (q.isLoading) return <Spinner />
  if (q.error) return <div className="page text-rot">{(q.error as Error).message}</div>
  const d = q.data!
  const w = d.widgets
  const noProjects = d.counts.active_projects === 0 && d.counts.inquiries === 0 && d.counts.offers === 0

  const redProjects = d.active_projects.filter((p) => p.signal === 'rot')
  const todayCount = d.overdue_tasks.length + d.today_tasks.length + redProjects.length
  const activeSorted = [...d.active_projects].sort((a, b) =>
    (SIGNAL_ORDER[a.signal] ?? 9) - (SIGNAL_ORDER[b.signal] ?? 9) || (a.deadline ?? '9999').localeCompare(b.deadline ?? '9999') || a.project_number.localeCompare(b.project_number))

  // Als Nächstes nach Tag gruppieren
  const byDay = new Map<string, Task[]>()
  for (const t of d.upcoming) byDay.set(t.due_date!, [...(byDay.get(t.due_date!) ?? []), t])

  return (
    <div className="page">
      <div className="mb-3 flex items-baseline gap-3 flex-wrap">
        <h1 className="text-[22px] font-semibold tracking-tight">{greeting(d.greeting_name)}</h1>
        <p className="text-muted text-[13px]">{fmtLong(d.today)} · KW {d.kw}</p>
      </div>

      {noProjects && (
        <div className="card p-5 mb-3">
          <p className="font-medium">Noch keine Projekte.</p>
          <p className="text-muted mt-1 text-[13px]">Leg das erste Projekt an. Mit einer Vorlage entstehen die Aufgaben samt Fristen automatisch. In den Einstellungen kannst du vorher Bearbeiter, Vorlagen und den Basispfad zum NAS prüfen.</p>
          <div className="mt-3 flex gap-2">
            <button className="btn-primary" onClick={ui.newProject}>Erstes Projekt anlegen</button>
            <Link to="/einstellungen" className="btn-outline">Einstellungen</Link>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 xl:grid-cols-6 gap-2 mb-3">
        <Stat label="Überfällig" value={d.counts.overdue} to="/aufgaben?bucket=ueberfaellig" tone="rot" />
        <Stat label="Heute fällig" value={d.counts.today} to="/aufgaben?bucket=heute" tone="orange" />
        <Stat label="Diese Woche" value={d.counts.this_week} to="/aufgaben?bucket=this_week" />
        <Stat label="Wartet" value={d.counts.waiting_tasks} to="/aufgaben?status=wartet" />
        <Stat label="Aktive Projekte" value={d.counts.active_projects} to="/projekte?filter=aktiv" />
        <Stat label="Kritisch" value={d.counts.critical_projects} to="/projekte?filter=kritisch" tone="rot" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,3fr)_minmax(300px,2fr)] gap-3">
        <div className="space-y-3 min-w-0">
          {w.heute !== false && (
            <Section title="Heute" count={todayCount} empty={todayCount === 0 ? 'Nichts überfällig, nichts für heute' : undefined}>
              {d.overdue_tasks.map((t) => <TaskRow key={t.id} t={t} onOpen={ui.openTask} railLevel="rot" />)}
              {d.today_tasks.map((t) => <TaskRow key={t.id} t={t} onOpen={ui.openTask} railLevel="orange" />)}
              {redProjects.length > 0 && (
                <div className={cx('mx-2.5', d.overdue_tasks.length + d.today_tasks.length > 0 && 'mt-1 pt-1.5 border-t')}>
                  {redProjects.map((p) => (
                    <Link key={p.id} to={`/projekte/${p.id}`} className="relative flex items-center gap-2.5 pl-3 pr-1 py-1.5 rounded-md row-hover">
                      <span className="rail bg-rot" />
                      <span className="font-medium">{p.project_number}</span>
                      <span className="truncate text-muted">{p.name}</span>
                      <RoundChip n={p.round_number} title={p.round_title} />
                      <span className="ml-auto text-[12px] text-muted shrink-0">{p.reasons.join(', ')}</span>
                    </Link>
                  ))}
                </div>
              )}
            </Section>
          )}

          {w.upcoming !== false && (
            <Section title="Als Nächstes" count={d.upcoming.length} to="/aufgaben?bucket=woche" empty={d.upcoming.length === 0 ? 'In den nächsten 7 Tagen ist nichts fällig' : undefined}>
              {[...byDay.entries()].map(([day, tasks]) => (
                <div key={day} className="mb-0.5">
                  <div className="px-2.5 pt-1.5 pb-0.5 text-[12px] text-muted flex items-baseline gap-2">
                    <span className="font-medium text-ink">{weekdayLong(day)}</span>{fmtDate(day, { year: false })}<span className="text-faint">{relDays(day)}</span>
                  </div>
                  {tasks.map((t) => <TaskRow key={t.id} t={t} onOpen={ui.openTask} dense railLevel="" />)}
                </div>
              ))}
            </Section>
          )}
        </div>

        <div className="space-y-3 min-w-0">
          <div ref={rightRef} className="space-y-3">
            {w.active_projects !== false && (
              <Section title="Aktive Projekte" count={activeSorted.length} to="/projekte?filter=aktiv" empty={activeSorted.length === 0 ? 'Keine aktiven Projekte. Anfragen und Angebote erscheinen hier, sobald sie beauftragt sind' : undefined}>
                {activeSorted.map((p) => <ProjectLine key={p.id} p={p} />)}
              </Section>
            )}

            {w.waiting !== false && (
              <Section title="Wartet auf Rückmeldung" count={d.waiting.length} to="/aufgaben?status=wartet" empty={d.waiting.length === 0 ? 'Nichts hängt gerade bei anderen' : undefined}>
                {d.waiting.map((t) => (
                  <button key={t.id} onClick={() => ui.openTask(t)} className="w-full text-left flex items-start gap-2.5 px-2.5 py-1.5 rounded-md row-hover">
                    <Clock size={14} className="text-muted mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <div className="font-medium truncate">{t.project_number} · {t.title}</div>
                      <div className="text-[12px] text-muted truncate">{t.waiting_for || 'Rückmeldung'}{t.waiting_on ? ` von ${t.waiting_on}` : ''}{t.waiting_since ? ` · seit ${fmtDate(t.waiting_since, { year: false })}` : ''}</div>
                    </div>
                  </button>
                ))}
              </Section>
            )}
          </div>

          {w.activity !== false && roomBelow && d.recent_activity.length > 0 && (
            <Section title="Zuletzt" to="/aktivitaeten">
              {d.recent_activity.slice(0, 6).map((a) => (
                <div key={a.id} className="px-2.5 py-1 text-[12.5px] flex gap-2">
                  <span className="text-faint shrink-0 w-[100px]">{fmtDateTime(a.created_at)}</span>
                  <span className="truncate"><span className="text-muted">{a.project_number}</span> {a.action}{a.task_title ? ` · ${a.task_title}` : ''}{a.new_value && a.field !== 'aufgabe' && a.field !== 'notiz' ? ` → ${a.new_value}` : ''}</span>
                </div>
              ))}
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}
