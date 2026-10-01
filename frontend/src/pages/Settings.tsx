import { useEffect, useState } from 'react'
import { Download, Plus, Trash2 } from 'lucide-react'
import type { Template, TemplateTask } from '@/api/types'
import { useAddHoliday, useBackups, useCreateBackup, useDeleteHoliday, useDeleteTaskType, useDeleteTemplate, useDeleteUser, useHolidays, useMeta, useSaveSettings, useSaveTaskType, useSaveTemplate, useSaveUser } from '@/api/hooks'
import { PageHeader } from '@/components/layout/Shell'
import { Confirm, Dialog, Field, Select, useToast } from '@/components/ui'
import { CATEGORY, cx, fmtDate, fmtDateTime } from '@/lib/format'

const WIDGETS: Array<[string, string]> = [['heute', 'Heute'], ['upcoming', 'Als Nächstes'], ['active_projects', 'Aktive Projekte'], ['waiting', 'Wartet auf Rückmeldung'], ['activity', 'Zuletzt']]

function Card({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="card">
      <header className="px-4 pt-3 pb-2 border-b"><h2 className="h2">{title}</h2>{sub && <p className="text-[12px] text-muted mt-0.5">{sub}</p>}</header>
      <div className="p-4">{children}</div>
    </section>
  )
}

export default function Settings() {
  const meta = useMeta().data
  const toast = useToast()
  const save = useSaveSettings()
  const [s, setS] = useState({ my_user_id: '', base_path: '', warn_workdays: 3, warn_project_workdays: 5, auto_backup: true, auto_create_folder: true, auto_rename_folder: true, dashboard_widgets: {} as Record<string, boolean> })
  useEffect(() => { if (meta) setS({ my_user_id: meta.settings.my_user_id ? String(meta.settings.my_user_id) : '', base_path: meta.settings.base_path, warn_workdays: meta.settings.warn_workdays, warn_project_workdays: meta.settings.warn_project_workdays, auto_backup: meta.settings.auto_backup, auto_create_folder: meta.settings.auto_create_folder, auto_rename_folder: meta.settings.auto_rename_folder, dashboard_widgets: meta.settings.dashboard_widgets }) }, [meta])
  const persist = (patch: Record<string, unknown>) => save.mutate(patch, { onSuccess: () => toast('Gespeichert'), onError: (e) => toast(e.message, 'error') })

  return (
    <div className="page-narrow">
      <PageHeader title="Einstellungen" sub={`Version ${meta?.version ?? ''} · Daten liegen lokal im Ordner data neben der Anwendung`} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Allgemein">
          <div className="space-y-3">
            <Field label="Ich bin" hint="bestimmt „Meine Aufgaben“ und den Standard-Bearbeiter">
              <Select value={s.my_user_id} onChange={(v) => { setS({ ...s, my_user_id: v }); persist({ my_user_id: Number(v) }) }} options={(meta?.users ?? []).map((u) => ({ value: u.id, label: u.name ? `${u.code} – ${u.name}` : u.code }))} />
            </Field>
            <Field label="Basispfad der Projektordner" hint={<>Ordner heißen <span className="text-ink">{'<Nr> <Anfrage|Auftrag> <Projektname>'}</span> im Jahresordner, z. B. 2026\26-301 Auftrag WP Testfeld</>}>
              <input className="input" value={s.base_path} onChange={(e) => setS({ ...s, base_path: e.target.value })} onBlur={() => persist({ base_path: s.base_path })} />
            </Field>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={s.auto_create_folder} onChange={(e) => { setS({ ...s, auto_create_folder: e.target.checked }); persist({ auto_create_folder: e.target.checked }) }} />Ordner beim Anlegen eines Projekts erstellen</label>
              <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={s.auto_rename_folder} onChange={(e) => { setS({ ...s, auto_rename_folder: e.target.checked }); persist({ auto_rename_folder: e.target.checked }) }} />Anfrage → Auftrag automatisch umbenennen</label>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="„Demnächst“ = Frist in ≤ Arbeitstagen"><input type="number" min={0} className="input" value={s.warn_workdays} onChange={(e) => setS({ ...s, warn_workdays: Number(e.target.value) })} onBlur={() => persist({ warn_workdays: s.warn_workdays })} /></Field>
              <Field label="Projekt gelb bei Frist in ≤ Arbeitstagen"><input type="number" min={0} className="input" value={s.warn_project_workdays} onChange={(e) => setS({ ...s, warn_project_workdays: Number(e.target.value) })} onBlur={() => persist({ warn_project_workdays: s.warn_project_workdays })} /></Field>
            </div>
            <div>
              <span className="label">Dashboard-Bereiche</span>
              <div className="grid grid-cols-2 gap-1.5">
                {WIDGETS.map(([k, l]) => (
                  <label key={k} className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={s.dashboard_widgets[k] !== false} onChange={(e) => { const w = { ...s.dashboard_widgets, [k]: e.target.checked }; setS({ ...s, dashboard_widgets: w }); persist({ dashboard_widgets: w }) }} />{l}</label>
                ))}
              </div>
            </div>
          </div>
        </Card>

        <Users />
        <Templates />
        <TaskTypes />
        <Holidays />
        <Backup autoBackup={s.auto_backup} onToggle={(v) => { setS({ ...s, auto_backup: v }); persist({ auto_backup: v }) }} />
      </div>
    </div>
  )
}

function Users() {
  const meta = useMeta().data
  const saveU = useSaveUser()
  const delU = useDeleteUser()
  const toast = useToast()
  const [n, setN] = useState({ code: '', name: '', role: '' })
  const [confirm, setConfirm] = useState<number | null>(null)
  return (
    <Card title="Bearbeiter" sub="Kürzel erscheinen bei Aufgaben und Projekten. Inaktive bleiben für alte Einträge erhalten.">
      <table className="w-full text-[13px]">
        <tbody>
          {(meta?.users ?? []).map((u) => (
            <tr key={u.id} className="border-b last:border-0">
              <td className="py-1.5 w-16 font-medium">{u.code}</td>
              <td className="py-1.5"><input className="input h-7" placeholder="Name" key={u.name} defaultValue={u.name} onBlur={(e) => e.target.value !== u.name && saveU.mutate({ id: u.id, data: { ...u, name: e.target.value } })} /></td>
              <td className="py-1.5 pl-2 w-32"><input className="input h-7" placeholder="Rolle" key={u.role} defaultValue={u.role} onBlur={(e) => e.target.value !== u.role && saveU.mutate({ id: u.id, data: { ...u, role: e.target.value } })} /></td>
              <td className="py-1.5 pl-2 w-20"><label className="flex items-center gap-1.5 text-[12px] text-muted"><input type="checkbox" checked={u.active} onChange={(e) => saveU.mutate({ id: u.id, data: { ...u, active: e.target.checked } })} />aktiv</label></td>
              <td className="py-1.5 w-8 text-right"><button className="text-faint hover:text-rot" onClick={() => setConfirm(u.id)} title="Löschen"><Trash2 size={13} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2 mt-3">
        <input className="input w-20" placeholder="Kürzel" value={n.code} onChange={(e) => setN({ ...n, code: e.target.value })} />
        <input className="input" placeholder="Name" value={n.name} onChange={(e) => setN({ ...n, name: e.target.value })} />
        <input className="input w-32" placeholder="Rolle" value={n.role} onChange={(e) => setN({ ...n, role: e.target.value })} />
        <button className="btn-outline" disabled={!n.code.trim()} onClick={() => saveU.mutate({ data: { ...n, active: true } }, { onSuccess: () => { setN({ code: '', name: '', role: '' }); toast('Bearbeiter angelegt') }, onError: (e) => toast(e.message, 'error') })}><Plus size={14} /></button>
      </div>
      <Confirm open={confirm !== null} onClose={() => setConfirm(null)} title="Bearbeiter löschen?" text="Geht nur, wenn keine Projekte oder Aufgaben mehr zugeordnet sind. Sonst besser auf inaktiv setzen."
        onConfirm={() => confirm && delU.mutate(confirm, { onError: (e) => toast(e.message, 'error') })} />
    </Card>
  )
}

function Templates() {
  const meta = useMeta().data
  const saveT = useSaveTemplate()
  const delT = useDeleteTemplate()
  const toast = useToast()
  const [edit, setEdit] = useState<Partial<Template> | null>(null)
  const [confirm, setConfirm] = useState<number | null>(null)
  const emptyTask = (): TemplateTask => ({ title: '', task_type_id: null, offset_workdays: null, weight: null, assignee_role: 'PL', depends_on_previous: true })
  const setTask = (i: number, patch: Partial<TemplateTask>) => setEdit((e) => ({ ...e!, tasks: e!.tasks!.map((t, j) => j === i ? { ...t, ...patch } : t) }))
  return (
    <Card title="Aufgabenvorlagen" sub="Offset = Arbeitstage vor der Projektfrist (negativ = danach). Rolle PL = Projektleiter, sonst Kürzel.">
      <ul className="divide-y">
        {(meta?.templates ?? []).map((t) => (
          <li key={t.id} className="py-2 flex items-center gap-3 text-[13px]">
            <div className="min-w-0 flex-1"><span className="font-medium">{t.name}</span>{t.category && <span className="ml-2 text-[11px] text-muted border rounded px-1.5">{CATEGORY[t.category]}</span>}<div className="text-[12px] text-muted truncate">{t.tasks.length} Aufgaben · {t.description}</div></div>
            <button className="btn-ghost btn-sm" onClick={() => setEdit({ ...t, tasks: t.tasks.map((x) => ({ ...x })) })}>Bearbeiten</button>
            <button className="text-faint hover:text-rot" onClick={() => setConfirm(t.id)} title="Löschen"><Trash2 size={13} /></button>
          </li>
        ))}
      </ul>
      <button className="btn-outline mt-3" onClick={() => setEdit({ name: '', description: '', category: null, sort_order: 99, tasks: [emptyTask()] })}><Plus size={14} />Neue Vorlage</button>

      <Dialog open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? `Vorlage „${edit.name}“` : 'Neue Vorlage'} width="max-w-3xl" footer={
        <>
          <button className="btn-outline" onClick={() => setEdit(null)}>Abbrechen</button>
          <button className="btn-primary" disabled={!edit?.name?.trim()} onClick={() => saveT.mutate({ id: edit!.id, data: { name: edit!.name, description: edit!.description ?? '', category: edit!.category, sort_order: edit!.sort_order ?? 0, tasks: (edit!.tasks ?? []).filter((t) => t.title.trim()).map((t) => ({ ...t, offset_workdays: t.offset_workdays === null || (t.offset_workdays as unknown) === '' ? null : Number(t.offset_workdays), weight: t.weight === null || (t.weight as unknown) === '' ? null : Number(t.weight) })) } }, { onSuccess: () => { setEdit(null); toast('Vorlage gespeichert') }, onError: (e) => toast(e.message, 'error') })}>Speichern</button>
        </>
      }>
        {edit && (
          <div className="space-y-3">
            <div className="grid grid-cols-[1fr_1fr_180px] gap-3">
              <Field label="Name"><input className="input" value={edit.name ?? ''} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
              <Field label="Beschreibung"><input className="input" value={edit.description ?? ''} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></Field>
              <Field label="Kategorie (Vorschlag beim Anlegen)"><Select value={edit.category ?? ''} onChange={(v) => setEdit({ ...edit, category: (v || null) as Template['category'] })} placeholder="–" options={Object.entries(CATEGORY).map(([value, label]) => ({ value, label }))} /></Field>
            </div>
            <table className="w-full text-[13px]">
              <thead><tr className="text-[11px] text-muted text-left"><th className="w-6"></th><th className="py-1">Aufgabe</th><th className="py-1 w-40">Aufgabenart</th><th className="py-1 w-20">Offset AT</th><th className="py-1 w-20">Gewicht</th><th className="py-1 w-20">Rolle</th><th className="py-1 w-20" title="Hängt von der vorigen Aufgabe ab">Vorgänger</th><th className="w-6"></th></tr></thead>
              <tbody>
                {(edit.tasks ?? []).map((t, i) => (
                  <tr key={i}>
                    <td className="text-faint text-[11px]">{i + 1}</td>
                    <td className="pr-2 py-0.5"><input className="input h-8" value={t.title} onChange={(e) => setTask(i, { title: e.target.value })} /></td>
                    <td className="pr-2 py-0.5"><Select className="h-8" value={t.task_type_id ?? ''} onChange={(v) => setTask(i, { task_type_id: v ? Number(v) : null })} placeholder="–" options={(meta?.task_types ?? []).map((x) => ({ value: x.id, label: x.name }))} /></td>
                    <td className="pr-2 py-0.5"><input type="number" className="input h-8" value={t.offset_workdays ?? ''} onChange={(e) => setTask(i, { offset_workdays: e.target.value === '' ? null : Number(e.target.value) })} /></td>
                    <td className="pr-2 py-0.5"><input type="number" step={0.5} className="input h-8" value={t.weight ?? ''} placeholder="Art" onChange={(e) => setTask(i, { weight: e.target.value === '' ? null : Number(e.target.value) })} /></td>
                    <td className="pr-2 py-0.5"><input className="input h-8" value={t.assignee_role} onChange={(e) => setTask(i, { assignee_role: e.target.value.toUpperCase() })} /></td>
                    <td className="py-0.5 text-center"><input type="checkbox" checked={t.depends_on_previous} onChange={(e) => setTask(i, { depends_on_previous: e.target.checked })} /></td>
                    <td className="text-right"><button className="text-faint hover:text-rot" onClick={() => setEdit({ ...edit, tasks: edit.tasks!.filter((_, j) => j !== i) })}><Trash2 size={13} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button className="btn-ghost btn-sm" onClick={() => setEdit({ ...edit, tasks: [...(edit.tasks ?? []), emptyTask()] })}><Plus size={13} />Aufgabe</button>
          </div>
        )}
      </Dialog>
      <Confirm open={confirm !== null} onClose={() => setConfirm(null)} title="Vorlage löschen?" text="Bereits angelegte Aufgaben in Projekten bleiben erhalten." onConfirm={() => confirm && delT.mutate(confirm)} />
    </Card>
  )
}

function TaskTypes() {
  const meta = useMeta().data
  const saveT = useSaveTaskType()
  const delT = useDeleteTaskType()
  const toast = useToast()
  const [n, setN] = useState({ name: '', default_weight: 1 })
  return (
    <Card title="Aufgabenarten" sub="Das Standardgewicht bestimmt, wie stark eine Aufgabe in den Projektfortschritt eingeht.">
      <table className="w-full text-[13px]">
        <tbody>
          {(meta?.task_types ?? []).map((t) => (
            <tr key={t.id} className="border-b last:border-0">
              <td className="py-1.5">{t.name}</td>
              <td className="py-1.5 w-24"><input type="number" step={0.5} min={0} className="input h-7" key={t.default_weight} defaultValue={t.default_weight} onBlur={(e) => Number(e.target.value) !== t.default_weight && saveT.mutate({ id: t.id, data: { ...t, default_weight: Number(e.target.value) } })} /></td>
              <td className="py-1.5 pl-3 w-8 text-right"><button className="text-faint hover:text-rot" onClick={() => delT.mutate(t.id, { onError: (e) => toast(e.message, 'error') })}><Trash2 size={13} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2 mt-3">
        <input className="input" placeholder="Neue Aufgabenart" value={n.name} onChange={(e) => setN({ ...n, name: e.target.value })} />
        <input type="number" step={0.5} className="input w-24" value={n.default_weight} onChange={(e) => setN({ ...n, default_weight: Number(e.target.value) })} />
        <button className="btn-outline" disabled={!n.name.trim()} onClick={() => saveT.mutate({ data: { ...n, sort_order: 99, active: true } }, { onSuccess: () => setN({ name: '', default_weight: 1 }), onError: (e) => toast(e.message, 'error') })}><Plus size={14} /></button>
      </div>
    </Card>
  )
}

function Holidays() {
  const q = useHolidays()
  const add = useAddHoliday()
  const del = useDeleteHoliday()
  const toast = useToast()
  const [n, setN] = useState({ date: '', name: '' })
  const list = (q.data ?? []).filter((h) => h.date >= new Date().getFullYear() + '-01-01')
  return (
    <Card title="Feiertage und freie Tage" sub="Werden bei Arbeitstagen, Fristen aus Vorlagen und Restlaufzeiten berücksichtigt.">
      <ul className="max-h-56 overflow-y-auto divide-y text-[13px]">
        {list.map((h) => <li key={h.id} className="py-1 flex items-center gap-3"><span className="w-24 text-muted">{fmtDate(h.date)}</span><span className="flex-1">{h.name}</span><button className="text-faint hover:text-rot" onClick={() => del.mutate(h.id)}><Trash2 size={13} /></button></li>)}
      </ul>
      <div className="flex gap-2 mt-3">
        <input type="date" className="input w-40" value={n.date} onChange={(e) => setN({ ...n, date: e.target.value })} />
        <input className="input" placeholder="Bezeichnung" value={n.name} onChange={(e) => setN({ ...n, name: e.target.value })} />
        <button className="btn-outline" disabled={!n.date} onClick={() => add.mutate(n, { onSuccess: () => setN({ date: '', name: '' }), onError: (e) => toast(e.message, 'error') })}><Plus size={14} /></button>
      </div>
    </Card>
  )
}

function Backup({ autoBackup, onToggle }: { autoBackup: boolean; onToggle: (v: boolean) => void }) {
  const q = useBackups()
  const create = useCreateBackup()
  const toast = useToast()
  return (
    <Card title="Export und Sicherung">
      <div className="flex flex-wrap gap-2">
        <a className="btn-outline" href="/api/export/excel"><Download size={14} />Excel-Export</a>
        <a className="btn-outline" href="/api/export/csv?what=tasks"><Download size={14} />Aufgaben als CSV</a>
        <a className="btn-outline" href="/api/export/csv?what=projects"><Download size={14} />Projekte als CSV</a>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button className="btn-primary" onClick={() => create.mutate(undefined, { onSuccess: (b) => toast(`Sicherung ${b.file} erstellt`), onError: (e) => toast(e.message, 'error') })}>Datenbank jetzt sichern</button>
        <label className="text-[13px] text-muted flex items-center gap-1.5"><input type="checkbox" checked={autoBackup} onChange={(e) => onToggle(e.target.checked)} />täglich beim Start sichern</label>
      </div>
      <p className="text-[12px] text-faint mt-2">Sicherungen liegen in data/backups, die letzten 30 werden behalten. Zum Wiederherstellen die Anwendung beenden und die Datei als data/projekte.db zurückkopieren.</p>
      <ul className={cx('mt-2 text-[12px] text-muted max-h-32 overflow-y-auto')}>
        {(q.data ?? []).slice(0, 10).map((b) => <li key={b.file} className="flex gap-3"><span className="w-32">{fmtDateTime(b.created_at)}</span><span>{b.file}</span><span className="text-faint">{Math.round(b.size_bytes / 1024)} KB</span></li>)}
      </ul>
    </Card>
  )
}
