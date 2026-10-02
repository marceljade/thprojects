import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Project } from '@/api/types'
import { useCreateProject, useFolderLookup, useMeta, useTemplatePreview, useUpdateProject } from '@/api/hooks'
import { DateInput, Dialog, Field, Select, useToast } from '@/components/ui'
import { CATEGORY, fmtDate, PRIORITY, PROJECT_STATUS, addDays, parseDate, toIso } from '@/lib/format'

const empty = {
  project_number: '', name: '', client: '', category: 'gutachten', assignee_id: '', participants: '', status: 'anfrage', priority: 'normal',
  request_date: '', offer_date: '', order_date: '', offered_weeks: '', target_deadline: '', folder_path: '', remarks: '', template_id: '', compute_due_dates: true,
}

const PHASE = (status: string) => (status === 'anfrage' || status === 'angebot' ? 'Anfrage' : 'Auftrag')
const sanitize = (s: string) => s.replace(/[\\/:*?"<>|]+/g, ' ').replace(/\s+/g, ' ').trim().replace(/\.+$/, '')
export function expectedFolder(base: string, nr: string, status: string, name: string): string | null {
  if (!base || !/^\d{2}-/.test(nr)) return null
  return `${base.replace(/[\\/]+$/, '')}\\20${nr.slice(0, 2)}\\${sanitize(`${nr} ${PHASE(status)} ${name}`)}`
}
/** Gegenstück zu folders.parse_folder_path: Nummer, Name und Status aus <Basis>\20JJ\<Nr> <Anfrage|Auftrag> <Name>. */
export function parseFolderPath(path: string): { project_number: string; name: string; status: 'anfrage' | 'beauftragt' } | null {
  let p = path.trim().replace(/^"|"$/g, '')
  if (p.toLowerCase().startsWith('file:///')) p = p.slice(8)
  p = p.replace(/[\\/]+$/, '')
  const last = p.split(/[\\/]/).pop() ?? ''
  const m = /^(\d{2}-\d{3})\s+(Anfrage|Auftrag)\s+(.+?)\s*$/.exec(last)
  if (!m) return null
  return { project_number: m[1], name: m[3], status: m[2] === 'Anfrage' ? 'anfrage' : 'beauftragt' }
}
type F = typeof empty

/** Projekt anlegen oder bearbeiten. Beim Anlegen mit Vorlagen-Vorschau samt berechneter Fristen. */
export function ProjectForm({ open, onClose, project }: { open: boolean; onClose: () => void; project?: Project | null }) {
  const meta = useMeta().data
  const create = useCreateProject()
  const update = useUpdateProject()
  const toast = useToast()
  const nav = useNavigate()
  const [f, setF] = useState<F>({ ...empty })
  const editing = !!project

  useEffect(() => {
    if (!open) return
    if (project) {
      setF({ ...empty, ...Object.fromEntries(Object.entries(project).filter(([k]) => k in empty).map(([k, v]) => [k, v ?? ''])) as Partial<F>, assignee_id: project.assignee_id ? String(project.assignee_id) : '', template_id: '' })
    } else {
      setF({ ...empty, assignee_id: meta?.settings.my_user_id ? String(meta.settings.my_user_id) : '' })
    }
  }, [open, project, meta])

  const set = (k: keyof F, v: string | boolean) => {
    // Pfad eingefügt -> Nummer, Name und Status aus dem Ordnernamen übernehmen, nur in noch leere Felder (beim Anlegen)
    const parsed = k === 'folder_path' && !editing && typeof v === 'string' ? parseFolderPath(v) : null
    const fill: Partial<F> = {}
    if (parsed) {
      if (!f.project_number.trim()) fill.project_number = parsed.project_number
      if (!f.name.trim()) fill.name = parsed.name
      // Status gilt als leer, solange noch der Startwert "Anfrage" steht
      if (f.status === 'anfrage' && parsed.status !== f.status) fill.status = parsed.status
    }
    setF((x) => {
      const n = { ...x, [k]: v, ...fill }
      // Auftragsdatum gesetzt -> Status wird "Beauftragt", solange noch Anfrage/Angebot steht
      if (k === 'order_date' && v && !editing && (x.status === 'anfrage' || x.status === 'angebot')) n.status = 'beauftragt'
      if (k === 'offer_date' && v && !editing && x.status === 'anfrage') n.status = 'angebot'
      return n
    })
    const taken = [fill.project_number && 'Projektnummer', fill.name && 'Projektname', fill.status && 'Status'].filter(Boolean)
    if (taken.length) toast(`${taken.join(', ')} aus dem Ordnernamen übernommen.`)
  }

  // Kategorie wechselt -> passende Vorlage vorschlagen (nur beim Anlegen)
  useEffect(() => {
    if (editing || !meta) return
    const tpl = meta.templates.find((t) => t.category === f.category)
    setF((x) => ({ ...x, template_id: tpl ? String(tpl.id) : x.template_id }))
  }, [f.category, meta, editing])

  const deadline = useMemo(() => {
    if (f.target_deadline) return f.target_deadline
    const od = parseDate(f.order_date)
    if (od && f.offered_weeks) return toIso(addDays(od, Math.round(Number(f.offered_weeks) * 7)))
    return null
  }, [f.target_deadline, f.order_date, f.offered_weeks])
  const lookup = useFolderLookup(f.project_number, f.status, f.name).data
  const preview = useTemplatePreview(f.template_id ? Number(f.template_id) : null, f.compute_due_dates ? deadline : null)

  const submit = () => {
    if (!f.project_number.trim()) return toast('Projektnummer fehlt.', 'error')
    if (!f.name.trim()) return toast('Projektname fehlt.', 'error')
    const data: Record<string, unknown> = {
      project_number: f.project_number.trim(), name: f.name.trim(), client: f.client, category: f.category, participants: f.participants,
      status: f.status, priority: f.priority, folder_path: f.folder_path, remarks: f.remarks,
      assignee_id: f.assignee_id ? Number(f.assignee_id) : null, offered_weeks: f.offered_weeks ? Number(f.offered_weeks) : null,
      request_date: f.request_date || null, offer_date: f.offer_date || null, order_date: f.order_date || null, target_deadline: f.target_deadline || null,
    }
    if (editing && project) {
      const clear = ['request_date', 'offer_date', 'order_date', 'target_deadline', 'offered_weeks', 'assignee_id'].filter((k) => data[k] === null)
      for (const k of clear) delete data[k]
      update.mutate({ id: project.id, data: { ...data, clear } }, { onSuccess: () => { toast('Projekt gespeichert'); onClose() }, onError: (e) => toast(e.message, 'error') })
    } else {
      data.template_id = f.template_id ? Number(f.template_id) : null
      data.compute_due_dates = f.compute_due_dates
      create.mutate(data, { onSuccess: (p) => { toast(`Projekt ${p.project_number} angelegt${p.folder_note ? ` · ${p.folder_note}` : ''}`); onClose(); nav(`/projekte/${p.id}`) }, onError: (e) => toast(e.message, 'error') })
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={editing ? `Projekt ${project?.project_number} bearbeiten` : 'Neues Projekt'} width="max-w-3xl" footer={
      <>
        <button className="btn-outline" onClick={onClose}>Abbrechen</button>
        <button className="btn-primary" onClick={submit} disabled={create.isPending || update.isPending}>{editing ? 'Speichern' : 'Projekt anlegen'}</button>
      </>
    }>
      <div className="grid grid-cols-1 md:grid-cols-[1fr_280px] gap-6">
        <div className="space-y-3">
          <div className="grid grid-cols-[130px_1fr] gap-3">
            <Field label="Projektnummer"><input className="input font-medium" autoFocus value={f.project_number} onChange={(e) => set('project_number', e.target.value)} placeholder="26-234" /></Field>
            <Field label="Projektname"><input className="input" value={f.name} onChange={(e) => set('name', e.target.value)} placeholder="z. B. WP Testfeld, Nachmessung" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Kategorie"><Select value={f.category} onChange={(v) => set('category', v)} options={Object.entries(CATEGORY).map(([value, label]) => ({ value, label }))} /></Field>
            <Field label="Auftraggeber"><input className="input" value={f.client} onChange={(e) => set('client', e.target.value)} /></Field>
            <Field label="Projektleiter"><Select value={f.assignee_id} onChange={(v) => set('assignee_id', v)} placeholder="–" options={(meta?.users ?? []).filter((u) => u.active).map((u) => ({ value: u.id, label: u.name ? `${u.code} – ${u.name}` : u.code }))} /></Field>
            <Field label="Beteiligte" hint="Kürzel, mit / getrennt"><input className="input" value={f.participants} onChange={(e) => set('participants', e.target.value)} /></Field>
            <Field label="Status"><Select value={f.status} onChange={(v) => set('status', v)} options={Object.entries(PROJECT_STATUS).map(([value, label]) => ({ value, label }))} /></Field>
            <Field label="Priorität"><Select value={f.priority} onChange={(v) => set('priority', v)} options={Object.entries(PRIORITY).map(([value, label]) => ({ value, label }))} /></Field>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Anfrage"><DateInput value={f.request_date} onChange={(v) => set('request_date', v)} /></Field>
            <Field label="Angebot"><DateInput value={f.offer_date} onChange={(v) => set('offer_date', v)} /></Field>
            <Field label="Auftrag"><DateInput value={f.order_date} onChange={(v) => set('order_date', v)} /></Field>
            <Field label="Dauer lt. Angebot (Wochen)"><input type="number" min={0} step={0.5} className="input" value={f.offered_weeks} onChange={(e) => set('offered_weeks', e.target.value)} /></Field>
            <Field label="Projektfrist (Ziel)" hint={deadline && !f.target_deadline ? `vertraglich: ${fmtDate(deadline)}` : 'überschreibt die vertragliche Frist'}>
              <DateInput value={f.target_deadline} onChange={(v) => set('target_deadline', v)} />
            </Field>
          </div>
          <Field label="Projektordner" hint={f.folder_path ? 'eigener Pfad' : (expectedFolder(meta?.settings.base_path ?? '', f.project_number, f.status, f.name)
            ? <>Erwarteter Ordner: <span className="text-ink break-all">{expectedFolder(meta?.settings.base_path ?? '', f.project_number, f.status, f.name)}</span>
                {lookup && <> · {lookup.found ? <span className="text-ink">gefunden{lookup.found.split(/[\\/]/).pop() !== expectedFolder(meta?.settings.base_path ?? '', f.project_number, f.status, f.name)?.split(/[\\/]/).pop() ? ` als ${lookup.found.split(/[\\/]/).pop()}` : ''}</span> : 'nicht gefunden, die App legt keinen an'}</>}</>
            : 'Basispfad in den Einstellungen setzen, dann wird ein vorhandener Ordner gefunden')}>
            <input className="input" value={f.folder_path} onChange={(e) => set('folder_path', e.target.value)} placeholder={editing ? 'leer = im Basispfad suchen' : 'leer = im Basispfad suchen, oder Pfad einfügen'} />
          </Field>
          <Field label="Bemerkung"><input className="input" value={f.remarks} onChange={(e) => set('remarks', e.target.value)} /></Field>
        </div>

        {!editing && (
          <div className="md:border-l md:pl-6">
            <Field label="Aufgaben aus Vorlage">
              <Select value={f.template_id} onChange={(v) => set('template_id', v)} placeholder="keine Vorlage" options={(meta?.templates ?? []).map((t) => ({ value: t.id, label: t.name }))} />
            </Field>
            <label className="flex items-center gap-2 mt-2 text-[13px] text-muted">
              <input type="checkbox" checked={f.compute_due_dates} onChange={(e) => set('compute_due_dates', e.target.checked)} />
              Fristen aus der Projektfrist berechnen
            </label>
            {f.template_id && (
              <div className="mt-3 text-[12.5px]">
                {!deadline && f.compute_due_dates && <p className="text-gelb mb-2">Ohne Auftragsdatum + Dauer oder Projektfrist bleiben die Fristen leer.</p>}
                <ol className="space-y-1">
                  {(preview.data ?? []).map((r, i) => (
                    <li key={i} className="flex items-baseline gap-2">
                      <span className="text-faint w-4 text-right">{i + 1}</span>
                      <span className="flex-1 truncate">{r.title}</span>
                      <span className="text-muted">{r.due_date ? fmtDate(r.due_date, { year: false }) : '–'}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        )}
      </div>
    </Dialog>
  )
}
