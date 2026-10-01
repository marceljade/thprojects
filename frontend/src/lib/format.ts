import type { Category, DueState, Priority, ProjectStatus, Signal, TaskStatus } from '@/api/types'

const WD = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa']
const WD_LONG = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag']
const MONTHS = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']

export function parseDate(s: string | null | undefined): Date | null {
  if (!s) return null
  const [y, m, d] = s.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function toIso(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function todayIso(): string { return toIso(new Date()) }

/** Datum aus eingefügtem Text: 15.10.2026, 15.10.26, 15.10. (aktuelles Jahr), 2026-10-15, 15/10/2026. Liefert ISO oder null. */
export function parsePastedDate(text: string): string | null {
  const t = (text ?? '').trim()
  let y = 0, m = 0, d = 0
  let r: RegExpMatchArray | null
  if ((r = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T\s].*)?$/))) { y = +r[1]; m = +r[2]; d = +r[3] }
  else if ((r = t.match(/^(\d{1,2})[./](\d{1,2})(?:[./](\d{2}|\d{4}))?\.?$/))) {
    d = +r[1]; m = +r[2]
    y = r[3] === undefined ? new Date().getFullYear() : r[3].length === 2 ? 2000 + +r[3] : +r[3]
  } else return null
  if (m < 1 || m > 12 || d < 1 || d > 31 || y < 1990 || y > 2100) return null
  const dt = new Date(y, m - 1, d)
  if (dt.getMonth() !== m - 1 || dt.getDate() !== d) return null
  return toIso(dt)
}

export function fmtDate(s: string | null | undefined, opts: { year?: boolean; weekday?: boolean } = {}): string {
  const d = parseDate(s)
  if (!d) return '–'
  const p = (n: number) => String(n).padStart(2, '0')
  const base = `${p(d.getDate())}.${p(d.getMonth() + 1)}.${opts.year === false ? '' : d.getFullYear()}`
  return opts.weekday ? `${WD[d.getDay()]}, ${base}` : base
}

export function fmtDateTime(s: string | null | undefined): string {
  if (!s) return '–'
  const d = new Date(s)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export function fmtLong(s: string): string {
  const d = parseDate(s)!
  return `${WD_LONG[d.getDay()]}, ${d.getDate()}. ${MONTHS[d.getMonth()]} ${d.getFullYear()}`
}

export function weekdayShort(s: string): string { return WD[parseDate(s)!.getDay()] }
export function weekdayLong(s: string): string { return WD_LONG[parseDate(s)!.getDay()] }
export function monthName(m: number): string { return MONTHS[m] }

export function isoWeek(d: Date): number {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const day = t.getUTCDay() || 7
  t.setUTCDate(t.getUTCDate() + 4 - day)
  const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1))
  return Math.ceil(((t.getTime() - y0.getTime()) / 86400000 + 1) / 7)
}

export function addDays(d: Date, n: number): Date { const x = new Date(d); x.setDate(x.getDate() + n); return x }
export function weekStart(d: Date): Date { const x = new Date(d); const wd = (x.getDay() + 6) % 7; x.setDate(x.getDate() - wd); x.setHours(0, 0, 0, 0); return x }
export function daysBetween(a: Date, b: Date): number { return Math.round((b.getTime() - a.getTime()) / 86400000) }

/** Relativ zu heute: „heute", „morgen", „in 3 Tagen", „vor 2 Tagen" */
export function relDays(s: string | null): string {
  const d = parseDate(s)
  if (!d) return 'ohne Frist'
  const n = daysBetween(new Date(new Date().setHours(0, 0, 0, 0)), d)
  if (n === 0) return 'heute'
  if (n === 1) return 'morgen'
  if (n === -1) return 'gestern'
  if (n > 0) return `in ${n} Tagen`
  return `vor ${-n} Tagen`
}

export const TASK_STATUS: Record<TaskStatus, string> = {
  nicht_begonnen: 'Nicht begonnen', geplant: 'Geplant', in_bearbeitung: 'In Bearbeitung', wartet: 'Wartet auf Rückmeldung', erledigt: 'Erledigt', entfaellt: 'Entfällt',
}
export const PROJECT_STATUS: Record<ProjectStatus, string> = {
  anfrage: 'Anfrage', angebot: 'Angebot erstellt', beauftragt: 'Beauftragt', in_bearbeitung: 'In Bearbeitung', wartet_kunde: 'Wartet auf Kunde',
  interne_pruefung: 'Interne Prüfung', abgeschlossen: 'Abgeschlossen', auf_eis: 'Auf Eis', abgelehnt: 'Abgelehnt / storniert',
}
export const PRIORITY: Record<Priority, string> = { niedrig: 'Niedrig', normal: 'Normal', hoch: 'Hoch', kritisch: 'Kritisch' }
export const CATEGORY: Record<Category, string> = { wea: 'WEA-Vermessung', messung: 'Messung', gutachten: 'Gutachten / Prognose', intern: 'Intern' }
export const CATEGORY_SHORT: Record<Category, string> = { wea: 'WEA', messung: 'Messung', gutachten: 'Gutachten', intern: 'Intern' }
export const DUE: Record<DueState, string> = {
  erledigt: 'Erledigt', ohne_frist: 'Ohne Frist', ueberfaellig: 'Überfällig', heute: 'Heute', demnaechst: 'Demnächst', woche: 'Diese Woche', spaeter: 'Später',
}
export const SIGNAL: Record<Signal, string> = { rot: 'Kritisch', gelb: 'Frist nähert sich', gruen: 'Im Plan', grau: 'Nicht aktiv', fertig: 'Abgeschlossen' }

/** Farbklassen für Fälligkeit (Textfarbe) */
export function dueColor(s: DueState): string {
  switch (s) {
    case 'ueberfaellig': return 'text-rot'
    case 'heute': return 'text-orange'
    case 'demnaechst': return 'text-gelb'
    case 'erledigt': return 'text-faint'
    default: return 'text-muted'
  }
}
export function signalBg(s: Signal): string {
  return { rot: 'bg-rot', gelb: 'bg-gelb', gruen: 'bg-gruen', grau: 'bg-faint', fertig: 'bg-line' }[s]
}
export function levelBg(l: string): string {
  return { rot: 'bg-rot', orange: 'bg-orange', gelb: 'bg-gelb', blau: 'bg-blau' }[l] ?? 'bg-faint'
}
export function dueLabel(t: { due_state: DueState; due_date: string | null; days_overdue: number }): string {
  if (t.due_state === 'ueberfaellig') return `${t.days_overdue} Tag${t.days_overdue === 1 ? '' : 'e'} überfällig`
  if (t.due_state === 'heute') return 'heute fällig'
  if (t.due_state === 'ohne_frist') return 'ohne Frist'
  if (t.due_state === 'erledigt') return 'erledigt'
  return `fällig ${fmtDate(t.due_date, { year: false })} · ${relDays(t.due_date)}`
}

export function cx(...parts: Array<string | false | null | undefined>): string { return parts.filter(Boolean).join(' ') }
