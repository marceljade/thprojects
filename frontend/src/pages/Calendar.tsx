import { useEffect, useRef, useState, type DragEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Flag, PanelRightClose, PanelRightOpen, RefreshCw } from 'lucide-react'
import type { CalendarDay, CalendarMark, Task } from '@/api/types'
import { useCalendar, useMeta, useOutlookSync, usePlanTask, useUnplanned } from '@/api/hooks'
import { useUi } from '@/components/layout/Shell'
import { Segmented, Select, Spinner, useToast } from '@/components/ui'
import { addDays, cx, fmtDate, isoWeek, monthName, toIso, todayIso, weekStart, weekdayShort, parseDate, PRIORITY } from '@/lib/format'

type View = 'woche' | 'monat'
const VIEWS: View[] = ['woche', 'monat']
const MONTH_MAX = 4

function loadView(): View {
  try { const v = localStorage.getItem('calendar_view'); if (v && (VIEWS as string[]).includes(v)) return v as View } catch { /* privat */ }
  return 'monat'
}
function loadPanel(): boolean {
  try { const v = localStorage.getItem('calendar_unplanned'); if (v === '0' || v === '1') return v === '1' } catch { /* privat */ }
  return typeof window !== 'undefined' ? window.innerWidth >= 1200 : true
}

/* Farbige linke Kante wie in TaskRow: rot überfällig oder nach Frist geplant, orange heute, sonst keine */
const edge = (t: Task) => t.status === 'erledigt' ? 'border-transparent' : t.due_state === 'ueberfaellig' || t.planned_after_due ? 'border-rot' : t.due_state === 'heute' || t.is_today ? 'border-orange' : 'border-transparent'
const canDrag = (t: Task) => t.is_open

type Drop = string | 'unplanned' | null

/** Ein Eintrag im Kalender oder in der Leiste. Ziehen verschiebt „geplant am“, Klick öffnet den Dialog. */
function Entry({ t, onOpen, onDragStart, onDragEnd, dense = false, project = true }:
  { t: Task; onOpen: (t: Task) => void; onDragStart: (t: Task) => void; onDragEnd: () => void; dense?: boolean; project?: boolean }) {
  const done = t.status === 'erledigt'
  const drag = canDrag(t)
  const warn = t.warnings.join(' · ')
  return (
    <div role="button" tabIndex={0} draggable={drag} data-task={t.id}
      onClick={() => onOpen(t)} onKeyDown={(e) => { if (e.key === 'Enter') onOpen(t) }}
      onDragStart={(e) => { if (!drag) { e.preventDefault(); return } e.dataTransfer.setData('text/plain', String(t.id)); e.dataTransfer.effectAllowed = 'move'; onDragStart(t) }}
      onDragEnd={onDragEnd}
      title={`${t.project_number} · ${t.title}${warn ? ` · ${warn}` : ''}${t.due_date && t.calendar_date !== t.due_date ? ` · Frist ${fmtDate(t.due_date, { year: false })}` : ''}`}
      className={cx('block w-full text-left rounded-r pl-1.5 pr-1 border-l-[3px] hover:bg-raised select-none', edge(t),
        dense ? 'py-0.5 leading-[16px] truncate' : 'py-1 text-[12.5px]', drag ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer', done && 'text-faint')}>
      {dense ? (
        <>{project && <span className={cx('mr-1', !done && 'text-muted')}>{t.project_number}</span>}<span className={cx(done && 'line-through')}>{t.title}</span></>
      ) : (
        <>
          <div className={cx('truncate', done ? 'line-through' : 'font-medium')}>{t.title}</div>
          {project && <div className={cx('text-[11.5px] truncate', done ? 'text-faint' : 'text-muted')}>{t.project_number} · {t.project_name}</div>}
          {!done && t.due_state === 'ueberfaellig' && <div className="text-[11px] text-rot">{t.days_overdue === 1 ? '1 Tag' : `${t.days_overdue} Tage`} überfällig</div>}
          {!done && warn && <div className={cx('text-[11px]', t.planned_after_due ? 'text-rot' : 'text-muted')}>{warn}</div>}
        </>
      )}
    </div>
  )
}

/** Frist- oder Projektfrist-Markierung, nicht verschiebbar. */
function Mark({ m, dense, onOpen }: { m: CalendarMark; dense: boolean; onOpen: () => void }) {
  const label = m.kind === 'project' ? `Projektfrist · ${m.project_number}` : `Frist: ${m.title}`
  return (
    <button onClick={onOpen} title={m.kind === 'project' ? `Projektfrist ${m.project_number} ${m.title}` : `Frist der Aufgabe „${m.title}“ (${m.project_number}), geplant an einem anderen Tag`}
      className={cx('flex items-center gap-1 w-full text-left text-faint italic pl-1 pr-1 border-l-[3px] border-dotted border-line truncate', dense ? 'py-0.5 leading-[16px] text-[11.5px]' : 'py-0.5 text-[11.5px]')}>
      <Flag size={10} className="shrink-0" /><span className="truncate">{label}</span>
    </button>
  )
}

export default function Calendar() {
  const [view, setViewState] = useState<View>(loadView)
  const setView = (v: View) => { setViewState(v); try { localStorage.setItem('calendar_view', v) } catch { /* privat */ } }
  const [panel, setPanelState] = useState<boolean>(loadPanel)
  const setPanel = (v: boolean) => { setPanelState(v); try { localStorage.setItem('calendar_unplanned', v ? '1' : '0') } catch { /* privat */ } }
  const [anchor, setAnchor] = useState(() => new Date())
  const [who, setWho] = useState('mine')
  const [withDone, setWithDone] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [drag, setDrag] = useState<Task | null>(null)
  const [over, setOver] = useState<Drop>(null)
  const meta = useMeta().data
  const outlook = useOutlookSync()
  const plan = usePlanTask()
  const qc = useQueryClient()
  const toast = useToast()
  const ui = useUi()

  let start: Date, end: Date, title: string
  if (view === 'woche') { start = weekStart(anchor); end = addDays(start, 6); title = `KW ${isoWeek(start)} · ${fmtDate(toIso(start), { year: false })} – ${fmtDate(toIso(end))}` }
  else { const m0 = new Date(anchor.getFullYear(), anchor.getMonth(), 1); start = weekStart(m0); end = addDays(weekStart(new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0)), 6); title = `${monthName(anchor.getMonth())} ${anchor.getFullYear()}` }
  const whoParams = { mine: who === 'mine', assignee_id: who !== 'mine' && who !== 'alle' ? Number(who) : undefined }
  const q = useCalendar(toIso(start), toIso(end), { ...whoParams, include_done: withDone })
  const unplanned = useUnplanned(whoParams)
  const step = (n: number) => setAnchor((a) => view === 'woche' ? addDays(a, 7 * n) : new Date(a.getFullYear(), a.getMonth() + n, 1))
  const days = q.data ?? []
  const today = todayIso()
  const weeks = Math.max(1, Math.round(days.length / 7))
  const isWeekend = (d: CalendarDay) => { const wd = parseDate(d.date)!.getDay(); return wd === 0 || wd === 6 }
  const weekCols = days.map((d) => (isWeekend(d) ? '88px' : 'minmax(0,1fr)')).join(' ')

  /* ---- Verschieben: sofort im Cache umsortieren, Server nachziehen, bei Fehler zurück */
  const move = (t: Task, target: Drop) => {
    setOver(null); setDrag(null)
    if (target === null) return
    const newPlanned = target === 'unplanned' ? null : target
    if (t.planned_date === newPlanned || (target === 'unplanned' && t.planned_date === null)) return
    const newDay = newPlanned ?? t.due_date
    const moved: Task = { ...t, planned_date: newPlanned, calendar_date: newDay, planned_after_due: !!(newPlanned && t.due_date && newPlanned > t.due_date) }
    const prevCal = qc.getQueriesData<CalendarDay[]>({ queryKey: ['calendar'] })
    const prevUn = qc.getQueriesData<Task[]>({ queryKey: ['unplanned'] })
    qc.setQueriesData<CalendarDay[]>({ queryKey: ['calendar'] }, (old) => old?.map((d) => {
      const rest = d.tasks.filter((x) => x.id !== t.id)
      return d.date === newDay ? { ...d, tasks: [...rest, moved] } : { ...d, tasks: rest }
    }))
    qc.setQueriesData<Task[]>({ queryKey: ['unplanned'] }, (old) => {
      const rest = (old ?? []).filter((x) => x.id !== t.id)
      return newDay === null ? [...rest, moved] : rest
    })
    plan.mutate({ id: t.id, planned_date: newPlanned }, {
      onSuccess: (r) => toast(newPlanned ? `„${r.title}“ geplant für ${fmtDate(newPlanned, { year: false })}${r.planned_after_due ? ' · nach Frist geplant' : ''}` : `„${r.title}“ ist wieder ungeplant`),
      onError: (e) => {
        for (const [k, v] of prevCal) qc.setQueryData(k, v)
        for (const [k, v] of prevUn) qc.setQueryData(k, v)
        toast(e.message, 'error')
      },
    })
  }
  const dropProps = (target: Drop) => ({
    onDragOver: (e: DragEvent) => { if (drag) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; if (over !== target) setOver(target) } },
    onDragLeave: (e: DragEvent) => { if (over === target && !(e.currentTarget as HTMLElement).contains(e.relatedTarget as Node)) setOver(null) },
    onDrop: (e: DragEvent) => { e.preventDefault(); if (drag) move(drag, target) },
  })
  const dragProps = { onDragStart: setDrag, onDragEnd: () => { setDrag(null); setOver(null) } }
  const openMark = (m: CalendarMark) => {
    if (m.kind === 'due' && m.task_id) {
      const t = days.flatMap((d) => d.tasks).find((x) => x.id === m.task_id)
      if (t) { ui.openTask(t); return }
    }
    window.location.hash = ''
    window.location.assign(`/projekte/${m.project_id}`)
  }

  /* ---- Leiste „Ungeplant“: nach Projekt, hoch zuerst */
  const groups = (() => {
    const by = new Map<string, { nr: string; name: string; tasks: Task[] }>()
    for (const t of unplanned.data ?? []) {
      const g = by.get(t.project_number) ?? { nr: t.project_number, name: t.project_name, tasks: [] }
      g.tasks.push(t); by.set(t.project_number, g)
    }
    return [...by.values()]
  })()

  // Höhe des Monatsrasters nur fürs Verhältnis der Zeilen, Einträge sind auf MONTH_MAX begrenzt
  const gridRef = useRef<HTMLDivElement>(null)
  useEffect(() => { setExpanded(new Set()) }, [anchor, view])

  const panelEl = (
    <aside {...dropProps('unplanned')} data-drop="unplanned"
      className={cx('card flex flex-col min-h-0 shrink-0 transition-[width]', panel ? 'w-[260px]' : 'w-[40px]', over === 'unplanned' && 'ring-2 ring-accent/60 bg-accent/5')}>
      <div className={cx('flex items-center border-b shrink-0', panel ? 'px-3 py-2 gap-2' : 'justify-center py-2')}>
        {panel && <h2 className="h2 text-[14px] flex-1">Ungeplant <span className="text-[12px] font-normal text-faint">{unplanned.data?.length ?? 0}</span></h2>}
        <button className="btn-icon h-7 w-7" onClick={() => setPanel(!panel)} title={panel ? 'Leiste einklappen' : 'Ungeplante Aufgaben zeigen'} aria-label={panel ? 'Leiste einklappen' : 'Leiste ausklappen'}>
          {panel ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
        </button>
      </div>
      {panel ? (
        <div className="flex-1 min-h-0 overflow-y-auto p-1.5 text-[12.5px]">
          {groups.length === 0 && <p className="text-faint px-2 py-2">Alles hat einen Tag. Neue Aufgaben ohne Frist landen hier.</p>}
          {groups.map((g) => (
            <div key={g.nr} className="mb-2">
              <div className="px-1.5 py-0.5 text-[11.5px] text-muted truncate" title={`${g.nr} ${g.name}`}><span className="font-medium text-ink">{g.nr}</span> · {g.name}</div>
              {g.tasks.map((t) => (
                <div key={t.id} className="flex items-center gap-1">
                  <div className="flex-1 min-w-0"><Entry t={t} onOpen={ui.openTask} {...dragProps} project={false} /></div>
                  {t.priority !== 'normal' && <span className={cx('text-[10.5px] shrink-0 pr-1', t.priority === 'kritisch' ? 'text-rot' : t.priority === 'hoch' ? 'text-orange' : 'text-faint')}>{PRIORITY[t.priority]}</span>}
                </div>
              ))}
            </div>
          ))}
          {drag && drag.planned_date && <p className="text-[11.5px] text-faint px-2 py-2 border-t mt-1">Hier ablegen hebt die Planung auf.</p>}
        </div>
      ) : (
        <div className="flex-1 flex items-start justify-center pt-2"><span className="text-[11px] text-faint [writing-mode:vertical-rl] rotate-180">Ungeplant {unplanned.data?.length ?? 0}</span></div>
      )}
    </aside>
  )

  return (
    <div className="page h-full flex flex-col min-h-0">
      <div className="flex items-center gap-2 mb-3 flex-wrap shrink-0">
        <h1 className="h1 mr-2">Kalender</h1>
        <button className="btn-icon h-8 w-8" onClick={() => step(-1)} aria-label="zurück"><ChevronLeft size={16} /></button>
        <button className="btn-outline btn-sm" onClick={() => setAnchor(new Date())}>Heute</button>
        <button className="btn-icon h-8 w-8" onClick={() => step(1)} aria-label="weiter"><ChevronRight size={16} /></button>
        <span className="font-medium ml-1 whitespace-nowrap">{title}</span>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <Segmented value={view} onChange={setView} options={[{ value: 'woche', label: 'Woche' }, { value: 'monat', label: 'Monat' }]} />
          <Select className="w-auto h-8 text-[12.5px]" value={who} onChange={setWho}
            options={[{ value: 'mine', label: `Meine (${meta?.settings.my_user_code ?? '–'})` }, { value: 'alle', label: 'Alle Bearbeiter' }, ...(meta?.users ?? []).filter((u) => u.active && u.id !== meta?.settings.my_user_id).map((u) => ({ value: String(u.id), label: u.code }))]} />
          <label className="text-[12px] text-muted flex items-center gap-1.5"><input type="checkbox" checked={withDone} onChange={(e) => setWithDone(e.target.checked)} />erledigte</label>
          {meta?.settings.outlook_sync === 'manuell' && (
            <button className="btn-outline btn-sm" disabled={outlook.isPending} title="Fristen in den Outlook-Ordner „Projektfristen“ schreiben"
              onClick={() => outlook.mutate(undefined, { onSuccess: (r) => toast(r.message), onError: (e) => toast(e.message, 'error') })}><RefreshCw size={13} />Mit Outlook abgleichen</button>
          )}
        </div>
      </div>

      <div className="flex gap-3 flex-1 min-h-0">
        <div className="flex-1 min-w-0 min-h-0 flex flex-col">
          {q.isLoading ? <Spinner /> : view === 'monat' ? (
            <div className="card overflow-hidden flex-1 min-h-0 flex flex-col">
              <div className="grid grid-cols-7 border-b text-[12px] text-muted shrink-0">
                {['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'].map((d) => <div key={d} className="px-2 py-1">{d}</div>)}
              </div>
              <div ref={gridRef} className="grid grid-cols-7 flex-1 min-h-0 overflow-y-auto" style={{ gridTemplateRows: `repeat(${weeks}, minmax(0, 1fr))` }}>
                {days.map((d, i) => {
                  const dt = parseDate(d.date)!
                  const other = dt.getMonth() !== anchor.getMonth()
                  const items: Array<{ key: string; el: JSX.Element }> = [
                    ...d.tasks.map((t) => ({ key: `t${t.id}`, el: <Entry t={t} onOpen={ui.openTask} {...dragProps} dense /> })),
                    ...d.marks.map((m, j) => ({ key: `m${j}`, el: <Mark m={m} dense onOpen={() => openMark(m)} /> })),
                  ]
                  const open = expanded.has(d.date)
                  const show = open || items.length <= MONTH_MAX ? items.length : MONTH_MAX - 1
                  const rest = items.length - show
                  return (
                    <div key={d.date} {...dropProps(d.date)} data-drop={d.date}
                      className={cx('min-h-0 border-b border-r p-1 text-[12px] flex flex-col', open ? 'overflow-y-auto' : 'overflow-hidden', i % 7 === 6 && 'border-r-0', i >= days.length - 7 && 'border-b-0',
                        !d.is_workday && 'bg-ink/[0.025]', other && 'opacity-50', d.date === today && 'bg-accent/5', over === d.date && 'ring-2 ring-inset ring-accent/60 bg-accent/10 opacity-100')}>
                      <div className="flex items-center justify-between h-[22px] mb-0.5 shrink-0">
                        <span className={cx('w-[22px] h-[22px] rounded-full flex items-center justify-center', d.date === today && 'bg-accent text-accent-ink font-medium')}>{dt.getDate()}</span>
                        {dt.getDay() === 1 && <span className="text-[10px] text-faint">KW {d.kw}</span>}
                        {d.holiday && <span className="text-[10px] text-gelb truncate ml-1" title={d.holiday}>{d.holiday}</span>}
                        {!d.holiday && d.tasks.length > 0 && <span className="text-[10px] text-faint">{d.tasks.length}</span>}
                      </div>
                      {items.slice(0, show).map((x) => <div key={x.key}>{x.el}</div>)}
                      {rest > 0 && <button className="text-faint text-left pl-1.5 leading-[16px] py-0.5 hover:text-ink" onClick={() => setExpanded((s) => { const n = new Set(s); n.add(d.date); return n })}>+{rest} weitere</button>}
                      {open && items.length > MONTH_MAX && <button className="text-faint text-left pl-1.5 leading-[16px] py-0.5 hover:text-ink" onClick={() => setExpanded((s) => { const n = new Set(s); n.delete(d.date); return n })}>weniger</button>}
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="grid gap-2 flex-1 min-h-0" style={{ gridTemplateColumns: weekCols }}>
              {days.map((d) => (
                <div key={d.date} {...dropProps(d.date)} data-drop={d.date}
                  className={cx('card min-w-0 flex flex-col min-h-0', d.date === today && 'border-accent/60', !d.is_workday && 'bg-ink/[0.02]', over === d.date && 'ring-2 ring-accent/60 bg-accent/5')}>
                  <div className={cx('px-2 py-1.5 border-b flex items-baseline gap-1.5 shrink-0 min-w-0', !d.is_workday && 'bg-ink/[0.025]')}>
                    <span className={cx('font-medium', d.date === today && 'text-accent')}>{weekdayShort(d.date)}</span>
                    <span className="text-muted text-[12px] truncate">{fmtDate(d.date, { year: false })}</span>
                    <span className={cx('text-[11px] ml-auto shrink-0 rounded-full px-1.5 min-w-[20px] text-center', d.tasks.length >= 6 ? 'bg-rot/10 text-rot' : d.tasks.length >= 4 ? 'bg-orange/10 text-orange' : 'text-faint')} title={`${d.tasks.length} Aufgaben`}>{d.tasks.length}</span>
                  </div>
                  {d.holiday && <div className="px-2 py-1 text-[11px] text-gelb truncate border-b" title={d.holiday}>{d.holiday}</div>}
                  <div className="p-1 flex-1 min-h-0 overflow-y-auto">
                    {d.tasks.length === 0 && d.marks.length === 0 && <p className="text-[12px] text-faint px-2 py-1.5">–</p>}
                    {d.tasks.map((t) => <Entry key={t.id} t={t} onOpen={ui.openTask} {...dragProps} dense={isWeekend(d)} />)}
                    {d.marks.map((m, j) => <Mark key={j} m={m} dense={isWeekend(d)} onOpen={() => openMark(m)} />)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {panelEl}
      </div>
    </div>
  )
}
