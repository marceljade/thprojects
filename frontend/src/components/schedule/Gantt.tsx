import { Link } from 'react-router-dom'
import type { Schedule, ScheduleProject, ScheduleTask } from '@/api/types'
import { addDays, cx, daysBetween, fmtDate, isoWeek, parseDate, signalBg, toIso, weekStart } from '@/lib/format'
import { Dot } from '@/components/ui'

const DAY = 16 // px je Tag
const LABEL = 260

function barClass(t: ScheduleTask): string {
  if (t.status === 'erledigt') return 'bg-gruen/70'
  if (t.status === 'entfaellt') return 'bg-line'
  if (t.due_state === 'ueberfaellig') return 'bg-rot'
  if (t.due_state === 'heute' || t.due_state === 'demnaechst') return 'bg-orange'
  if (t.status === 'wartet') return 'bg-blau'
  return 'bg-accent'
}

/** Zeitplan: Wochenachse oben, je Projekt ein Block mit einer Zeile je Aufgabe. */
export function Gantt({ data, onTask, compact = false, showProjectHeader = true }:
  { data: Schedule; onTask?: (id: number) => void; compact?: boolean; showProjectHeader?: boolean }) {
  const start = weekStart(parseDate(data.start)!)
  const end = parseDate(data.end)!
  const days = daysBetween(start, end) + 1
  const today = parseDate(data.today)!
  const weeks: Array<{ x: number; kw: number; label: string }> = []
  for (let d = new Date(start); d <= end; d = addDays(d, 7)) weeks.push({ x: daysBetween(start, d) * DAY, kw: isoWeek(d), label: fmtDate(toIso(d), { year: false }) })
  const holidays = new Set(data.holidays.map((h) => h.date))
  const width = days * DAY

  const x = (iso: string) => Math.max(0, daysBetween(start, parseDate(iso)!)) * DAY

  const Row = ({ t }: { t: ScheduleTask }) => {
    const left = x(t.start)
    const w = Math.max(DAY, (daysBetween(parseDate(t.start)!, parseDate(t.end)!) + 1) * DAY)
    return (
      <div className={cx('flex items-center border-b border-line/60', compact ? 'h-7' : 'h-8')}>
        <div className="shrink-0 pl-5 pr-2 truncate text-[12.5px] flex items-center gap-1.5" style={{ width: LABEL }}>
          <span className={cx('truncate', t.status === 'erledigt' && 'text-faint line-through')}>{t.title}</span>
          {t.assignee_code && <span className="text-[10.5px] text-faint shrink-0">{t.assignee_code}</span>}
        </div>
        <div className="relative flex-1 h-full" style={{ width }}>
          <button onClick={() => onTask?.(t.id)} title={`${t.title}: ${fmtDate(t.start)} – ${fmtDate(t.end)}${t.predecessor_open ? ' · Vorgänger noch offen' : ''}`}
            className={cx('absolute top-1/2 -translate-y-1/2 h-[14px] rounded-sm hover:brightness-110 transition', barClass(t))}
            style={{ left, width: w - 2 }} />
        </div>
      </div>
    )
  }

  const Block = ({ p }: { p: ScheduleProject }) => (
    <div>
      {showProjectHeader && (
        <div className="flex items-center h-9 bg-raised/70 border-b sticky left-0">
          <div className="shrink-0 px-3 flex items-center gap-2 text-[13px] truncate" style={{ width: LABEL }}>
            <Dot className={signalBg(p.signal)} />
            <Link to={`/projekte/${p.id}`} className="font-medium hover:text-accent">{p.project_number}</Link>
            <span className="text-muted truncate">{p.name}</span>
          </div>
          <div className="relative flex-1 h-full" style={{ width }}>
            {p.deadline && parseDate(p.deadline)! >= start && parseDate(p.deadline)! <= end && (
              <div className="absolute top-0 bottom-0 border-l-2 border-dashed border-rot/60" style={{ left: x(p.deadline) + DAY - 1 }} title={`Projektfrist ${fmtDate(p.deadline)}`}>
                <span className="absolute -top-0 left-1 text-[10px] text-rot whitespace-nowrap">Frist {fmtDate(p.deadline, { year: false })}</span>
              </div>
            )}
          </div>
        </div>
      )}
      {p.tasks.map((t) => <Row key={t.id} t={t} />)}
      {!showProjectHeader && p.deadline && parseDate(p.deadline)! >= start && parseDate(p.deadline)! <= end && (
        <div className="relative h-5"><div className="absolute text-[10.5px] text-rot" style={{ left: LABEL + x(p.deadline) + DAY + 3 }}>Projektfrist {fmtDate(p.deadline, { year: false })}</div></div>
      )}
    </div>
  )

  return (
    <div className="overflow-x-auto">
      <div className="relative" style={{ minWidth: LABEL + width }}>
        {/* Kopf: Wochen */}
        <div className="flex h-9 border-b sticky top-0 bg-surface z-10">
          <div className="shrink-0 px-3 text-[12px] text-muted flex items-center" style={{ width: LABEL }}>Aufgabe</div>
          <div className="relative flex-1" style={{ width }}>
            {weeks.map((w) => (
              <div key={w.x} className="absolute top-0 bottom-0 border-l border-line/70 pl-1.5 text-[11px] leading-[36px] whitespace-nowrap" style={{ left: w.x, width: DAY * 7 }}>
                <span className="font-medium text-ink">KW {w.kw}</span> <span className="text-faint">{w.label}</span>
              </div>
            ))}
          </div>
        </div>
        {/* Hintergrund: Wochenenden, Feiertage, Heute */}
        <div className="absolute top-9 bottom-0 pointer-events-none" style={{ left: LABEL, width }}>
          {Array.from({ length: days }, (_, i) => {
            const d = addDays(start, i)
            const iso = toIso(d)
            const we = d.getDay() === 0 || d.getDay() === 6
            const hol = holidays.has(iso)
            if (!we && !hol) return null
            return <div key={i} className={cx('absolute top-0 bottom-0', hol ? 'bg-gelb/15' : 'bg-ink/[0.035]')} style={{ left: i * DAY, width: DAY }} />
          })}
          {today >= start && today <= end && <div className="absolute top-0 bottom-0 w-[2px] bg-accent" style={{ left: daysBetween(start, today) * DAY + DAY / 2 }} />}
        </div>
        {data.projects.map((p) => <Block key={p.id} p={p} />)}
        {data.projects.length === 0 && <div className="py-10 text-center text-muted text-[13px]">Keine Aufgaben mit Datum in diesem Zeitraum.</div>}
      </div>
    </div>
  )
}
