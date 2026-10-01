import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowDown, ArrowUp, CheckCheck, FolderOpen, FolderSync, LayoutTemplate, Pencil, Plus, Trash2 } from 'lucide-react'
import type { Task } from '@/api/types'
import { useApplyTemplate, useCompleteProject, useCreateNote, useDeleteNote, useDeleteProject, useMeta, useOpenFolder, useProject, useReorderTasks, useSchedule, useSyncFolder, useUpdateProject } from '@/api/hooks'
import { useUi } from '@/components/layout/Shell'
import { Gantt } from '@/components/schedule/Gantt'
import { PriorityMark } from '@/components/tasks/TaskRow'
import { CheckCircle, Confirm, Dialog, Dot, Field, ProgressBar, Select, Spinner, useToast } from '@/components/ui'
import { useCompleteTask, useReopenTask } from '@/api/hooks'
import { CATEGORY, cx, dueColor, dueLabel, fmtDate, fmtDateTime, PRIORITY, PROJECT_STATUS, signalBg, SIGNAL, TASK_STATUS } from '@/lib/format'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { Activity } from '@/api/types'

export default function ProjectDetail() {
  const { id } = useParams()
  const pid = Number(id)
  const q = useProject(pid)
  const meta = useMeta().data
  const ui = useUi()
  const nav = useNavigate()
  const toast = useToast()
  const update = useUpdateProject()
  const del = useDeleteProject()
  const complete = useCompleteProject()
  const applyTpl = useApplyTemplate()
  const openFolder = useOpenFolder()
  const syncFolder = useSyncFolder()
  const reorder = useReorderTasks()
  const addNote = useCreateNote()
  const delNote = useDeleteNote()
  const completeTask = useCompleteTask()
  const reopenTask = useReopenTask()
  const schedule = useSchedule({ project_id: pid, include_done: true })
  const activity = useQuery({ queryKey: ['activity', { project_id: pid }], queryFn: () => api.get<Activity[]>(`/api/projects/${pid}/activity?limit=50`), enabled: !!pid })
  const [tab, setTab] = useState<'notizen' | 'aktivitaet'>('notizen')
  const [note, setNote] = useState('')
  const [confirmDel, setConfirmDel] = useState(false)
  const [doneDlg, setDoneDlg] = useState(false)
  const [tplDlg, setTplDlg] = useState(false)
  const [tplId, setTplId] = useState('')
  const [tplDeadline, setTplDeadline] = useState('')
  const [showDone, setShowDone] = useState(true)

  if (q.isLoading) return <Spinner />
  if (q.error || !q.data) return <div className="page text-rot">Projekt nicht gefunden. <Link to="/projekte" className="underline">Zur Projektliste</Link></div>
  const p = q.data
  const tasks = p.tasks.filter((t) => showDone || t.is_open)
  const openCount = p.tasks.filter((t) => t.is_open).length

  const setStatus = (v: string) => update.mutate({ id: p.id, data: { status: v } }, { onSuccess: (r) => toast(r.folder_note ? `Status geändert · ${r.folder_note}` : 'Status geändert'), onError: (e) => toast(e.message, 'error') })
  const setPriority = (v: string) => update.mutate({ id: p.id, data: { priority: v } })
  const setAssignee = (v: string) => update.mutate({ id: p.id, data: v ? { assignee_id: Number(v) } : { clear: ['assignee_id'] } })
  const move = (t: Task, dir: -1 | 1) => {
    const ids = p.tasks.map((x) => x.id)
    const i = ids.indexOf(t.id)
    const j = i + dir
    if (j < 0 || j >= ids.length) return
    ;[ids[i], ids[j]] = [ids[j], ids[i]]
    reorder.mutate({ projectId: p.id, ids })
  }
  const doOpenFolder = () => openFolder.mutate(p.id, {
    onSuccess: (r) => { if (r.opened) toast('Ordner geöffnet'); else { navigator.clipboard?.writeText(r.path); toast(`${r.message ?? 'Pfad'} ${r.path}`) } },
    onError: (e) => toast(e.message, 'error'),
  })

  return (
    <div className="page">
      <div className="text-[12px] text-muted mb-2"><Link to="/projekte" className="hover:text-accent">Projekte</Link> / {CATEGORY[p.category]}</div>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="text-[26px] font-semibold tracking-tight">{p.project_number}</h1>
            <span className="inline-flex items-center gap-1.5 text-[12px] text-muted"><Dot className={signalBg(p.signal)} />{SIGNAL[p.signal]}</span>
          </div>
          <p className="text-[16px] text-ink mt-0.5">{p.name}</p>
          {(p.reasons.length > 0 || p.warnings.length > 0) && (
            <p className="text-[12.5px] mt-1"><span className={p.signal === 'rot' ? 'text-rot' : p.signal === 'gelb' ? 'text-gelb' : 'text-muted'}>{p.reasons.join(' · ')}</span>{p.reasons.length > 0 && p.warnings.length > 0 && <span className="text-faint"> · </span>}<span className="text-muted">{p.warnings.join(' · ')}</span></p>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button className="btn-outline" onClick={doOpenFolder} disabled={openFolder.isPending}><FolderOpen size={14} />Projektordner öffnen</button>
          <button className="btn-outline" onClick={() => ui.editProject(p)}><Pencil size={14} />Bearbeiten</button>
          <button className="btn-outline" onClick={() => { setTplId(meta?.templates.find((t) => t.category === p.category)?.id.toString() ?? ''); setTplDeadline(p.deadline ?? ''); setTplDlg(true) }}><LayoutTemplate size={14} />Vorlage anwenden</button>
          {!p.folder_matches && <button className="btn-outline border-gelb/50" title={`Ordner umbenennen in „${p.expected_folder_name}“`} onClick={() => syncFolder.mutate(p.id, { onSuccess: (r) => toast(r.message, r.ok ? 'ok' : 'error'), onError: (e) => toast(e.message, 'error') })}><FolderSync size={14} />Ordner abgleichen</button>}
          {p.status !== 'abgeschlossen' && <button className="btn-outline" onClick={() => setDoneDlg(true)}><CheckCheck size={14} />Abschließen</button>}
          <button className="btn-ghost text-rot" onClick={() => setConfirmDel(true)} title="Projekt löschen"><Trash2 size={14} /></button>
        </div>
      </div>

      <div className="card px-4 py-3 mb-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-6 gap-y-3 text-[13px]">
        <Field label="Status"><Select className="h-8" value={p.status} onChange={setStatus} options={Object.entries(PROJECT_STATUS).map(([value, label]) => ({ value, label }))} /></Field>
        <Field label="Priorität"><Select className="h-8" value={p.priority} onChange={setPriority} options={Object.entries(PRIORITY).map(([value, label]) => ({ value, label }))} /></Field>
        <Field label="Projektleiter"><Select className="h-8" value={p.assignee_id ?? ''} onChange={setAssignee} placeholder="–" options={(meta?.users ?? []).filter((u) => u.active || u.id === p.assignee_id).map((u) => ({ value: u.id, label: u.code }))} /></Field>
        <div><span className="label">Fortschritt</span><div className="pt-2"><ProgressBar value={p.progress} size="md" /></div><div className="text-[11px] text-faint mt-1">{openCount} von {p.task_count} Aufgaben offen</div></div>
        <div><span className="label">Projektfrist</span>
          <div className="pt-1.5 font-medium">{p.deadline ? fmtDate(p.deadline) : <span className="text-faint font-normal">keine</span>}{p.deadline_kw && <span className="text-faint font-normal text-[12px]"> KW {p.deadline_kw}</span>}</div>
          <div className="text-[11px] text-faint mt-1">{p.remaining_workdays !== null ? (p.remaining_workdays >= 0 ? `noch ${p.remaining_workdays} Arbeitstage` : `${-p.remaining_workdays} Arbeitstage überschritten`) : p.target_deadline ? 'Ziel' : p.contractual_deadline ? 'vertraglich' : ''}</div>
        </div>
        <div><span className="label">Auftraggeber</span><div className="pt-1.5 truncate">{p.client || <span className="text-faint">–</span>}</div>
          <div className="text-[11px] text-faint mt-1">{[p.request_date && `Anfrage ${fmtDate(p.request_date, { year: false })}`, p.offer_date && `Angebot ${fmtDate(p.offer_date, { year: false })}`, p.order_date && `Auftrag ${fmtDate(p.order_date, { year: false })}`, p.offered_weeks && `${p.offered_weeks} Wo.`].filter(Boolean).join(' · ')}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)] gap-4">
        <div className="space-y-4 min-w-0">
          <section className="card">
            <header className="flex items-center justify-between px-4 pt-3 pb-2">
              <h2 className="h2">Aufgaben <span className="text-[12px] font-normal text-faint">{openCount} offen</span></h2>
              <div className="flex items-center gap-2">
                <label className="text-[12px] text-muted flex items-center gap-1.5"><input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} />erledigte zeigen</label>
                <button className="btn-outline btn-sm" onClick={() => ui.newTask(p.id)}><Plus size={13} />Aufgabe</button>
              </div>
            </header>
            {tasks.length === 0 ? (
              <p className="px-4 pb-4 text-muted text-[13px]">Noch keine Aufgaben. Über „Vorlage anwenden" entstehen die Standardaufgaben mit Fristen.</p>
            ) : (
              <div className="px-1.5 pb-2">
                {tasks.map((t, i) => (
                  <div key={t.id} className="group flex items-center gap-3 pl-3 pr-2 py-2 rounded-md row-hover cursor-pointer" onClick={() => ui.openTask(t)}>
                    <CheckCircle checked={t.status === 'erledigt'} onChange={() => t.status === 'erledigt' ? reopenTask.mutate(t.id) : completeTask.mutate(t.id, { onSuccess: () => toast(`„${t.title}“ erledigt`) })} />
                    <span className="w-5 text-[11px] text-faint text-right">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2"><span className={cx('truncate', t.status === 'erledigt' ? 'text-faint line-through' : 'font-medium')}>{t.title}</span><PriorityMark p={t.priority} />{t.predecessor_open && ['ueberfaellig', 'heute', 'demnaechst', 'woche'].includes(t.due_state) && <span className="text-[11px] text-gelb whitespace-nowrap shrink-0" title="Die vorige Aufgabe ist noch offen">Vorgänger offen</span>}</div>
                      <div className="text-[12px] text-muted">{TASK_STATUS[t.status]}{t.task_type_name ? ` · ${t.task_type_name}` : ''}{t.status === 'wartet' && t.waiting_for ? ` · ${t.waiting_for}${t.waiting_on ? ` von ${t.waiting_on}` : ''}` : ''}</div>
                    </div>
                    <span className="w-9 h-6 rounded bg-raised border text-[11px] text-muted flex items-center justify-center shrink-0">{t.assignee_code ?? '–'}</span>
                    <div className="w-32 hidden sm:block"><ProgressBar value={t.progress} /></div>
                    <div className={cx('w-32 text-right text-[12px] shrink-0', dueColor(t.due_state))}>{t.due_date ? <>{fmtDate(t.due_date, { year: false })}<span className="text-faint"> KW {t.kw}</span></> : '–'}<div className="text-[11px]">{t.is_open ? dueLabel(t).replace(/^fällig .*? · /, '') : ''}</div></div>
                    <div className="flex flex-col opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                      <button className="text-faint hover:text-ink h-3.5" onClick={() => move(t, -1)} title="nach oben"><ArrowUp size={12} /></button>
                      <button className="text-faint hover:text-ink h-3.5" onClick={() => move(t, 1)} title="nach unten"><ArrowDown size={12} /></button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="card">
            <header className="px-4 pt-3 pb-2"><h2 className="h2">Zeitplan</h2></header>
            {schedule.data ? <Gantt data={schedule.data} compact showProjectHeader={false} onTask={(tid) => { const t = p.tasks.find((x) => x.id === tid); if (t) ui.openTask(t) }} /> : <Spinner />}
          </section>
        </div>

        <div className="space-y-4 min-w-0">
          <section className="card">
            <header className="flex items-center gap-4 px-4 pt-3 pb-2 border-b">
              <button className={cx('h2 pb-1 border-b-2 -mb-[9px]', tab === 'notizen' ? 'border-accent' : 'border-transparent text-muted')} onClick={() => setTab('notizen')}>Notizen <span className="text-[12px] font-normal text-faint">{p.notes.length}</span></button>
              <button className={cx('h2 pb-1 border-b-2 -mb-[9px]', tab === 'aktivitaet' ? 'border-accent' : 'border-transparent text-muted')} onClick={() => setTab('aktivitaet')}>Historie</button>
            </header>
            {tab === 'notizen' ? (
              <div className="p-3">
                <textarea className="input-area min-h-[60px]" placeholder="Notiz schreiben … (Strg+Enter speichert)" value={note} onChange={(e) => setNote(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && note.trim()) addNote.mutate({ project_id: p.id, content: note }, { onSuccess: () => { setNote(''); toast('Notiz gespeichert') } }) }} />
                <div className="flex justify-end mt-2"><button className="btn-primary btn-sm" disabled={!note.trim()} onClick={() => addNote.mutate({ project_id: p.id, content: note }, { onSuccess: () => { setNote(''); toast('Notiz gespeichert') } })}>Notiz speichern</button></div>
                <ul className="mt-3 space-y-3">
                  {p.notes.map((n) => (
                    <li key={n.id} className="group text-[13px]">
                      <div className="flex items-center gap-2 text-[12px] text-faint"><span className="font-medium text-muted">{n.author_code ?? '–'}</span>{fmtDateTime(n.created_at)}{n.task_title && <span className="truncate">· {n.task_title}</span>}
                        <button className="ml-auto opacity-0 group-hover:opacity-100 text-faint hover:text-rot" title="Notiz löschen" onClick={() => delNote.mutate(n.id)}><Trash2 size={12} /></button></div>
                      <div className="whitespace-pre-wrap mt-0.5">{n.content}</div>
                    </li>
                  ))}
                  {p.notes.length === 0 && <li className="text-muted text-[13px]">Noch keine Notizen.</li>}
                </ul>
              </div>
            ) : (
              <ul className="p-3 space-y-2 text-[12.5px]">
                {(activity.data ?? []).map((a) => (
                  <li key={a.id} className="flex gap-2"><span className="text-faint shrink-0 w-[108px]">{fmtDateTime(a.created_at)}</span>
                    <span><span className="text-muted">{a.user_code} · </span>{a.action}{a.task_title ? ` · ${a.task_title}` : ''}{a.field && a.field !== 'aufgabe' && a.field !== 'notiz' && a.field !== 'vorlage' ? ` (${a.field}${a.old_value ? `: ${a.old_value} →` : ':'} ${a.new_value || '–'})` : a.new_value && a.field !== 'aufgabe' ? `: ${a.new_value}` : ''}{a.details ? ` · ${a.details}` : ''}</span></li>
                ))}
              </ul>
            )}
          </section>
          {p.remarks && <section className="card px-4 py-3 text-[13px]"><span className="label">Bemerkung</span>{p.remarks}</section>}
          <section className="card px-4 py-3 text-[12px] text-muted break-all"><span className="label">Projektordner</span>
            {p.folder_path || <span className="text-faint">keiner hinterlegt</span>}
            {!p.folder_matches && <div className="mt-1 text-gelb">Erwartet: {p.expected_folder_name} – „Ordner abgleichen“ benennt um{p.folder_path ? '' : ' oder legt an'}.</div>}
          </section>
        </div>
      </div>

      <Confirm open={confirmDel} onClose={() => setConfirmDel(false)} title="Projekt löschen?" text={`${p.project_number} mit ${p.task_count} Aufgaben und ${p.notes.length} Notizen wird endgültig gelöscht.`}
        onConfirm={() => del.mutate(p.id, { onSuccess: () => { toast('Projekt gelöscht'); nav('/projekte') } })} />

      <Dialog open={doneDlg} onClose={() => setDoneDlg(false)} title="Projekt abschließen" width="max-w-md" footer={
        <>
          <button className="btn-outline" onClick={() => setDoneDlg(false)}>Abbrechen</button>
          {openCount > 0 && <button className="btn-outline" onClick={() => complete.mutate({ id: p.id, open_tasks: 'entfaellt' }, { onSuccess: () => { setDoneDlg(false); toast('Projekt abgeschlossen') } })}>Offene auf „Entfällt"</button>}
          <button className="btn-primary" onClick={() => complete.mutate({ id: p.id, open_tasks: 'erledigt' }, { onSuccess: () => { setDoneDlg(false); toast('Projekt abgeschlossen') } })}>{openCount > 0 ? 'Offene erledigen und abschließen' : 'Abschließen'}</button>
        </>
      }>
        <p className="text-muted">{openCount > 0 ? `${openCount} Aufgaben sind noch offen. Was soll damit passieren?` : 'Das Projekt wird auf „Abgeschlossen" gesetzt, Fertigstellung heute.'}</p>
      </Dialog>

      <Dialog open={tplDlg} onClose={() => setTplDlg(false)} title="Vorlage anwenden" width="max-w-md" footer={
        <>
          <button className="btn-outline" onClick={() => setTplDlg(false)}>Abbrechen</button>
          <button className="btn-primary" disabled={!tplId} onClick={() => applyTpl.mutate({ id: p.id, data: { template_id: Number(tplId), deadline: tplDeadline || null, compute_due_dates: !!tplDeadline } }, { onSuccess: (r) => { setTplDlg(false); toast(`${r.task_count - p.task_count} Aufgaben angelegt`) }, onError: (e) => toast(e.message, 'error') })}>Aufgaben anlegen</button>
        </>
      }>
        <div className="space-y-3">
          <Field label="Vorlage"><Select value={tplId} onChange={setTplId} placeholder="wählen …" options={(meta?.templates ?? []).map((t) => ({ value: t.id, label: t.name }))} /></Field>
          <Field label="Fristen rückwärts rechnen ab" hint="leer = Aufgaben ohne Frist anlegen"><input type="date" className="input" value={tplDeadline} onChange={(e) => setTplDeadline(e.target.value)} /></Field>
          <p className="text-[12px] text-muted">Die Aufgaben werden an die bestehende Liste angehängt.</p>
        </div>
      </Dialog>
    </div>
  )
}
