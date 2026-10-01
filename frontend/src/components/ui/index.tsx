import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { Check, X } from 'lucide-react'
import { cx, parsePastedDate } from '@/lib/format'

/* ------------------------------------------------------------------ Toast */
interface ToastMsg { id: number; text: string; kind: 'ok' | 'error' }
const ToastCtx = createContext<(text: string, kind?: 'ok' | 'error') => void>(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [list, setList] = useState<ToastMsg[]>([])
  const push = useCallback((text: string, kind: 'ok' | 'error' = 'ok') => {
    const id = Date.now() + Math.random()
    setList((l) => [...l, { id, text, kind }])
    setTimeout(() => setList((l) => l.filter((t) => t.id !== id)), kind === 'error' ? 6000 : 2800)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 pointer-events-none">
        {list.map((t) => (
          <div key={t.id} role="status" className={cx('pointer-events-auto card shadow-pop px-3.5 py-2.5 text-[13px] flex items-center gap-2 max-w-sm',
            t.kind === 'error' ? 'border-rot/40 text-rot' : 'text-ink')}>
            {t.kind === 'ok' && <Check size={14} className="text-gruen shrink-0" />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

/* ----------------------------------------------------------------- Dialog */
export function Dialog({ open, onClose, title, children, width = 'max-w-xl', footer }:
  { open: boolean; onClose: () => void; title: string; children: ReactNode; width?: string; footer?: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    const first = ref.current?.querySelector<HTMLElement>('input, select, textarea, button')
    first?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/30 dark:bg-black/50 p-4 sm:p-8" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={ref} role="dialog" aria-modal="true" aria-label={title} className={cx('card shadow-pop w-full my-auto', width)}>
        <div className="flex items-center justify-between px-5 py-3.5 border-b">
          <h2 className="h2">{title}</h2>
          <button className="btn-icon h-8 w-8" onClick={onClose} aria-label="Schließen"><X size={16} /></button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="px-5 py-3 border-t flex items-center justify-end gap-2 bg-raised/60 rounded-b-lg">{footer}</div>}
      </div>
    </div>
  )
}

export function Confirm({ open, onClose, onConfirm, title, text, confirmLabel = 'Löschen', danger = true }:
  { open: boolean; onClose: () => void; onConfirm: () => void; title: string; text: string; confirmLabel?: string; danger?: boolean }) {
  return (
    <Dialog open={open} onClose={onClose} title={title} width="max-w-md" footer={
      <>
        <button className="btn-outline" onClick={onClose}>Abbrechen</button>
        <button className={danger ? 'btn-danger' : 'btn-primary'} onClick={() => { onConfirm(); onClose() }}>{confirmLabel}</button>
      </>
    }>
      <p className="text-muted">{text}</p>
    </Dialog>
  )
}

/* ------------------------------------------------------------- Formulare */
export function Field({ label, children, hint, className }: { label: string; children: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <label className={cx('block', className)}>
      <span className="label">{label}</span>
      {children}
      {hint && <span className="block mt-1 text-[12px] text-faint">{hint}</span>}
    </label>
  )
}

/** Datumsfeld: tippen, Kalender oder Datum einfügen (15.10.2026, 15.10.26, 2026-10-15). Wert immer ISO oder leer. */
export function DateInput({ value, onChange, onBlur, className, disabled }:
  { value: string | null | undefined; onChange: (v: string) => void; onBlur?: () => void; className?: string; disabled?: boolean }) {
  const toast = useToast()
  return (
    <input type="date" className={cx('input', className)} value={value ?? ''} disabled={disabled}
      onChange={(e) => onChange(e.target.value)} onBlur={onBlur}
      onPaste={(e) => {
        const text = e.clipboardData.getData('text')
        if (!text.trim()) return
        e.preventDefault()
        const iso = parsePastedDate(text)
        if (iso) onChange(iso)
        else toast(`„${text.trim()}“ ist kein Datum. Erwartet wird TT.MM.JJJJ.`, 'error')
      }} />
  )
}

export function Select({ value, onChange, options, placeholder, className, disabled }:
  { value: string | number | null | undefined; onChange: (v: string) => void; options: Array<{ value: string | number; label: string }>; placeholder?: string; className?: string; disabled?: boolean }) {
  return (
    <select className={cx('input appearance-none pr-8 bg-no-repeat bg-[right_0.6rem_center] bg-[length:14px]', className)}
      style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%239aa3ab' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")" }}
      value={value ?? ''} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

/* ------------------------------------------------------------- Anzeigen */
export function ProgressBar({ value, className, size = 'sm' }: { value: number; className?: string; size?: 'sm' | 'md' }) {
  return (
    <div className={cx('flex items-center gap-2', className)} title={`${value} %`}>
      <div className={cx('flex-1 rounded-full bg-line overflow-hidden', size === 'sm' ? 'h-1.5' : 'h-2')}>
        <div className={cx('h-full rounded-full transition-[width] duration-300', value >= 100 ? 'bg-gruen' : 'bg-accent')} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
      <span className="text-[12px] text-muted w-9 text-right">{value} %</span>
    </div>
  )
}

export function Dot({ className, size = 8 }: { className: string; size?: number }) {
  return <span className={cx('inline-block rounded-full shrink-0', className)} style={{ width: size, height: size }} />
}

export function EmptyState({ title, text, action }: { title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="py-10 text-center">
      <p className="text-ink font-medium">{title}</p>
      {text && <p className="text-muted mt-1 text-[13px]">{text}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}

export function Spinner() {
  return <div className="py-12 text-center text-faint text-[13px]">Lädt …</div>
}

/* Runder Haken zum Abhaken – das zentrale Bedienelement */
export function CheckCircle({ checked, onChange, label }: { checked: boolean; onChange: () => void; label?: string }) {
  return (
    <button type="button" role="checkbox" aria-checked={checked} aria-label={label ?? (checked ? 'Wieder öffnen' : 'Erledigt')}
      onClick={(e) => { e.stopPropagation(); onChange() }}
      className={cx('shrink-0 w-[18px] h-[18px] rounded-full border-[1.5px] flex items-center justify-center transition-colors',
        checked ? 'bg-gruen border-gruen text-white' : 'border-faint hover:border-accent hover:bg-accent/10 text-transparent hover:text-accent')}>
      <Check size={12} strokeWidth={3} />
    </button>
  )
}

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: Array<{ value: T; label: string; count?: number }> }) {
  return (
    <div className="inline-flex items-center gap-1 flex-wrap">
      {options.map((o) => (
        <button key={o.value} className={o.value === value ? 'chip-on' : 'chip'} onClick={() => onChange(o.value)}>
          {o.label}{o.count !== undefined && <span className={cx('ml-1.5 text-[11px]', o.value === value ? 'opacity-70' : 'text-faint')}>{o.count}</span>}
        </button>
      ))}
    </div>
  )
}
