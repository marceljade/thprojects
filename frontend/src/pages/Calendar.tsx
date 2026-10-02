import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import type { CalendarDay, Task } from '@/api/types'
import { useCalendar, useMeta, useOutlookSync } from '@/api/hooks'
import { useUi } from '@/components/layout/Shell'
import { TaskRow } from '@/components/tasks/TaskRow'
import { Segmented, Select, Spinner, useToast } from '@/components/ui'
import { addDays, cx, fmtDate, fmtLong, isoWeek, monthName, toIso, todayIso, weekStart, weekdayShort, parseDate } from '@/lib/format'

type View = 'tag' | 'woche' | 'monat'
const VIEWS: View[] = ['tag', 'woche', 'monat']

function loadView(): View {
  try { const v = localStorage.getItem('calendar_view'); if (v && (VIEWS as string[]).includes(v)) return v as View } catch { /* privat */ }
  return 'monat'
}

/** Höhe eines Elements, aktualisiert bei Größenänderung (für die Zellenberechnung im Monat).
 *  `active` sagt, ob das Element gerade gerendert wird, damit der Beobachter nach Laden/Ansichtswechsel neu anbindet. */
function useHeight<T extends HTMLElement>(active: boolean) {
  const ref = useRef<T>(null)
  const [h, setH] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!active || !el) return
    const ro = new ResizeObserver(() => setH(el.clientHeight))
    ro.observe(el)
    setH(el.clientHeight)
    return () => ro.disconnect()
  }, [active])
  return [ref, h] as const
}

/* Farbige linke Kante wie in TaskRow: rot überfällig, orange heute, sonst keine */
const edge = (t: Task) => t.status === 'erledigt' ? '' : t.due_state === 'ueberfaellig' ? 'border-rot' : t.due_state === 'heute' ? 'border-orange' : 'border-transparent'

function CellTask({ t, onOpen, project = true }: { t: Task; onOpen: (t: Task) => void; project?: boolean }) {
  const done = t.status === 'erledigt'
  return (
    <button onClick={() => onOpen(t)} title={`${t.project_number} · ${t.title}`}
      className={cx('block w-full text-left truncate rounded-r pl-1.5 pr-1 py-0.5 border-l-[3px] hover:bg-raised leading-[16px]', edge(t), done && 'line-through text-faint')}>
      {project && <span className={cx('mr-1', !done && 'text-muted')}>{t.project_number}</span>}{t.title}
    </button>
  )
}

export default function Calendar() {
  const [view, setViewState] = useState<View>(loadView)
  const setView = (v: View) => { setViewState(v); try { localStorage.setItem('calendar_view', v) } catch { /* privat */ } }
  const [anchor, setAnchor] = useState(() => new Date())
  const [who, setWho] = useState('mine')
  const [withDone, setWithDone] = useState(false)
  const meta = useMeta().data
  const outlook = useOutlookSync()
  const toast = useToast()
  const ui = useUi()

  let start: Date, end: Date, title: string
  if (view === 'tag') { start = new Date(anchor); end = new Date(anchor); title = fmtLong(toIso(anchor)) }
  else if (view === 'woche') { start = weekStart(anchor); end = addDays(start, 6); title = `KW ${isoWeek(start)} · ${fmtDate(toIso(start), { year: false })} – ${fmtDate(toIso(end))}` }
  else { const m0 = new Date(anchor.getFullYear(), anchor.getMonth(), 1); start = weekStart(m0); end = addDays(weekStart(new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0)), 6); title = `${monthName(anchor.getMonth())} ${anchor.getFullYear()}` }
  const q = useCalendar(toIso(start), toIso(end), { mine: who === 'mine', assignee_id: who !== 'mine' && who !== 'alle' ? Number(who) : undefined, include_done: withDone })
  const [gridRef, gridH] = useHeight<HTMLDivElement>(view === 'monat' && !q.isLoading)
  const step = (n: number) => setAnchor((a) => view === 'tag' ? addDays(a, n) : view === 'woche' ? addDays(a, 7 * n) : new Date(a.getFullYear(), a.getMonth() + n, 1))
  const days = q.data ?? []
  const today = todayIso()

  // Monat: Zeilen = Wochen, Platz je Zelle aus der Rasterhöhe, Aufgabenzeile 20 px, Datumszeile 26 px
  const weeks = Math.max(1, Math.round(days.length / 7))
  const cellH = gridH / weeks
  const fit = Math.max(0, Math.floor((cellH - 26 - 6) / 20))
  const visibleCount = (n: number) => (n <= fit ? n : Math.max(0, fit - 1))

  // Woche: Sa/So nur breit, wenn dort Aufgaben liegen
  const isWeekend = (d: CalendarDay) => { const wd = parseDate(d.date)!.getDay(); return wd === 0 || wd === 6 }
  const narrow = (d: CalendarDay) => view === 'woche' && isWeekend(d) && d.tasks.length === 0
  const weekCols = days.map((d) => (narrow(d) ? '28px' : 'minmax(0,1fr)')).join(' ')

  return (
    <div className="page h-full flex flex-col min-h-0">
      <div className="flex items-center gap-2 mb-3 flex-wrap shrink-0">
        <h1 className="h1 mr-2">Kalender</h1>
        <button className="btn-icon h-8 w-8" onClick={() => step(-1)} aria-label="zurück"><ChevronLeft size={16} /></button>
        <button className="btn-outline btn-sm" onClick={() => setAnchor(new Date())}>Heute</button>
        <button className="btn-icon h-8 w-8" onClick={() => step(1)} aria-label="weiter"><ChevronRight size={16} /></button>
        <span className="font-medium ml-1 whitespace-nowrap">{title}</span>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <Segmented value={view} onChange={setView} options={[{ value: 'tag', label: 'Tag' }, { value: 'woche', label: 'Woche' }, { value: 'monat', label: 'Monat' }]} />
          <Select className="w-auto h-8 text-[12.5px]" value={who} onChange={setWho}
            options={[{ value: 'mine', label: `Meine (${meta?.settings.my_user_code ?? '–'})` }, { value: 'alle', label: 'Alle Bearbeiter' }, ...(meta?.users ?? []).filter((u) => u.active && u.id !== meta?.settings.my_user_id).map((u) => ({ value: String(u.id), label: u.code }))]} />
          <label className="text-[12px] text-muted flex items-center gap-1.5"><input type="checkbox" checked={withDone} onChange={(e) => setWithDone(e.target.checked)} />erledigte</label>
          {meta?.settings.outlook_sync === 'manuell' && (
            <button className="btn-outline btn-sm" disabled={outlook.isPending} title="Fristen in den Outlook-Ordner „Projektfristen“ schreiben"
              onClick={() => outlook.mutate(undefined, { onSuccess: (r) => toast(r.message), onError: (e) => toast(e.message, 'error') })}><RefreshCw size={13} />Mit Outlook abgleichen</button>
          )}
        </div>
      </div>

      {q.isLoading ? <Spinner /> : view === 'monat' ? (
        <div className="card overflow-hidden flex-1 min-h-0 flex flex-col">
          <div className="grid grid-cols-7 border-b text-[12px] text-muted shrink-0">
            {['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'].map((d) => <div key={d} className="px-2 py-1">{d}</div>)}
          </div>
          <div ref={gridRef} className="grid grid-cols-7 flex-1 min-h-0" style={{ gridTemplateRows: `repeat(${weeks}, minmax(0, 1fr))` }}>
            {days.map((d, i) => {
              const dt = parseDate(d.date)!
              const other = dt.getMonth() !== anchor.getMonth()
              const show = visibleCount(d.tasks.length)
              const rest = d.tasks.length - show
              return (
                <div key={d.date} className={cx('min-h-0 overflow-hidden border-b border-r p-1 text-[12px] flex flex-col', i % 7 === 6 && 'border-r-0', i >= days.length - 7 && 'border-b-0',
                  !d.is_workday && 'bg-ink/[0.025]', other && 'opacity-50', d.date === today && 'bg-accent/5')}>
                  <div className="flex items-center justify-between h-[22px] mb-0.5 shrink-0">
                    <span className={cx('w-[22px] h-[22px] rounded-full flex items-center justify-center', d.date === today && 'bg-accent text-accent-ink font-medium')}>{dt.getDate()}</span>
                    {dt.getDay() === 1 && <span className="text-[10px] text-faint">KW {d.kw}</span>}
                    {d.holiday && <span className="text-[10px] text-gelb truncate ml-1" title={d.holiday}>{d.holiday}</span>}
                  </div>
                  {d.tasks.slice(0, show).map((t) => <CellTask key={t.id} t={t} onOpen={ui.openTask} />)}
                  {rest > 0 && <div className="text-faint pl-1.5 leading-[16px] py-0.5">+{rest} weitere</div>}
                </div>
              )
            })}
          </div>
        </div>
      ) : view === 'woche' ? (
        <div className="grid gap-2 flex-1 min-h-0" style={{ gridTemplateColumns: weekCols }}>
          {days.map((d) => narrow(d) ? (
            <div key={d.date} className={cx('card min-w-0 flex flex-col items-center pt-2 text-[11px] text-faint bg-ink/[0.025]', d.date === today && 'border-accent/60')} title={`${weekdayShort(d.date)} ${fmtDate(d.date, { year: false })}`}>
              <span className={cx(d.date === today && 'text-accent font-medium')}>{weekdayShort(d.date)}</span>
            </div>
          ) : (
            <div key={d.date} className={cx('card min-w-0 flex flex-col min-h-0', d.date === today && 'border-accent/60')}>
              <div className={cx('px-2.5 py-1.5 border-b flex items-baseline gap-2 shrink-0', !d.is_workday && 'bg-ink/[0.025]')}>
                <span className={cx('font-medium', d.date === today && 'text-accent')}>{weekdayShort(d.date)}</span>
                <span className="text-muted text-[12px]">{fmtDate(d.date, { year: false })}</span>
                {d.holiday && <span className="text-[11px] text-gelb ml-auto truncate" title={d.holiday}>{d.holiday}</span>}
                {!d.holiday && d.tasks.length > 0 && <span className="text-[11px] text-faint ml-auto">{d.tasks.length}</span>}
              </div>
              <div className="p-1 flex-1 min-h-0 overflow-y-auto">
                {d.tasks.length === 0 && <p className="text-[12px] text-faint px-2 py-1.5">–</p>}
                {d.tasks.map((t) => {
                  const done = t.status === 'erledigt'
                  return (
                    <button key={t.id} onClick={() => ui.openTask(t)} className={cx('w-full text-left pl-2 pr-1.5 py-1 rounded-r row-hover text-[12.5px] border-l-[3px]', edge(t), done && 'text-faint')}>
                      <div className={cx('truncate', done ? 'line-through' : 'font-medium')}>{t.title}</div>
                      <div className={cx('text-[11.5px] truncate', done ? 'text-faint' : 'text-muted')}>{t.project_number} · {t.project_name}</div>
                      {!done && t.due_state === 'ueberfaellig' && <div className="text-[11px] text-rot">{t.days_overdue === 1 ? '1 Tag' : `${t.days_overdue} Tage`} überfällig</div>}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto">
          {days.map((d) => (
            <div key={d.date} className={cx('card min-w-0', d.date === today && 'border-accent/60')}>
              <div className={cx('px-3 py-1.5 border-b flex items-baseline gap-2', !d.is_workday && 'bg-ink/[0.025]')}>
                <span className={cx('font-medium', d.date === today && 'text-accent')}>{weekdayShort(d.date)}</span>
                <span className="text-muted text-[12px]">{fmtDate(d.date, { year: false })}</span>
                {d.holiday && <span className="text-[11px] text-gelb ml-auto truncate">{d.holiday}</span>}
                {!d.holiday && d.tasks.length > 0 && <span className="text-[11px] text-faint ml-auto">{d.tasks.length}</span>}
              </div>
              <div className="px-1 py-1">
                {d.tasks.length === 0 && <p className="text-[12px] text-faint px-2 py-2">Nichts fällig an diesem Tag.</p>}
                {d.tasks.map((t) => <TaskRow key={t.id} t={t} onOpen={ui.openTask} />)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
