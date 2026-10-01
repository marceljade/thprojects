import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Activity, Bell, CalendarDays, ChevronsLeft, ChevronsRight, FolderKanban, GanttChartSquare, LayoutDashboard, ListTodo, Moon, Plus, Search, Settings, Sun } from 'lucide-react'
import type { Project, Task } from '@/api/types'
import { useMeta, useNotifications, useSearch } from '@/api/hooks'
import { TaskDialog } from '@/components/tasks/TaskDialog'
import { TaskForm } from '@/components/tasks/TaskForm'
import { ProjectForm } from '@/components/projects/ProjectForm'
import { cx, dueColor, dueLabel, levelBg, fmtDateTime } from '@/lib/format'
import { Dot } from '@/components/ui'

/* -------------------------------------------------------------- UI-Kontext */
interface Ui {
  openTask: (t: Task) => void
  newTask: (projectId?: number) => void
  newProject: () => void
  editProject: (p: Project) => void
}
const UiCtx = createContext<Ui>({ openTask: () => {}, newTask: () => {}, newProject: () => {}, editProject: () => {} })
export const useUi = () => useContext(UiCtx)

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  const toggle = useCallback(() => {
    setDark((d) => {
      const n = !d
      document.documentElement.classList.toggle('dark', n)
      try { localStorage.setItem('theme', n ? 'dark' : 'light') } catch { /* privat */ }
      return n
    })
  }, [])
  return { dark, toggle }
}

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/aufgaben', label: 'Aufgaben', icon: ListTodo },
  { to: '/projekte', label: 'Projekte', icon: FolderKanban },
  { to: '/kalender', label: 'Kalender', icon: CalendarDays },
  { to: '/zeitplan', label: 'Zeitplan', icon: GanttChartSquare },
  { to: '/aktivitaeten', label: 'Aktivitäten', icon: Activity },
  { to: '/einstellungen', label: 'Einstellungen', icon: Settings },
]

export function Shell() {
  const [collapsed, setCollapsed] = useState(() => { try { const v = localStorage.getItem('sidebar'); if (v) return v === 'closed' } catch { /* privat */ } return window.innerWidth < 1400 })
  const [task, setTask] = useState<Task | null>(null)
  const [newTaskFor, setNewTaskFor] = useState<number | undefined | false>(false)
  const [projectDlg, setProjectDlg] = useState<{ open: boolean; project?: Project | null }>({ open: false })
  const { dark, toggle } = useTheme()
  const meta = useMeta().data
  const loc = useLocation()

  useEffect(() => { try { localStorage.setItem('sidebar', collapsed ? 'closed' : 'open') } catch { /* privat */ } }, [collapsed])

  const ui = useMemo<Ui>(() => ({
    openTask: (t) => setTask(t),
    newTask: (pid) => setNewTaskFor(pid),
    newProject: () => setProjectDlg({ open: true, project: null }),
    editProject: (p) => setProjectDlg({ open: true, project: p }),
  }), [])

  // Tastaturkürzel: n = neue Aufgabe, p = neues Projekt, / = Suche
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'n') { e.preventDefault(); setNewTaskFor(undefined) }
      if (e.key === 'p') { e.preventDefault(); setProjectDlg({ open: true, project: null }) }
      if (e.key === '/') { e.preventDefault(); document.getElementById('global-search')?.focus() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <UiCtx.Provider value={ui}>
      <div className="flex h-full">
        <aside className={cx('shrink-0 border-r bg-surface flex flex-col transition-[width] duration-200', collapsed ? 'w-14' : 'w-56')}>
          <div className={cx('flex items-center h-14 border-b px-3 gap-2', collapsed && 'justify-center px-0')}>
            <span className="w-7 h-7 rounded-md bg-accent text-accent-ink flex items-center justify-center shrink-0">
              <svg viewBox="0 0 32 32" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M8 20l4-8 4 8 4-8 4 8" /></svg>
            </span>
            {!collapsed && <span className="font-semibold tracking-tight truncate">Projekte T&amp;H</span>}
          </div>
          <nav className="flex-1 py-2 px-2 space-y-0.5">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} title={label}
                className={({ isActive }) => cx('flex items-center gap-2.5 h-9 rounded-md px-2.5 text-[13.5px] transition-colors',
                  isActive ? 'bg-raised text-ink font-medium' : 'text-muted hover:text-ink hover:bg-raised/70', collapsed && 'justify-center px-0')}>
                <Icon size={17} className="shrink-0" />
                {!collapsed && <span>{label}</span>}
              </NavLink>
            ))}
          </nav>
          <div className="p-2 border-t">
            <button className={cx('btn-ghost w-full', collapsed ? 'px-0' : 'justify-start')} onClick={() => setCollapsed((c) => !c)} title={collapsed ? 'Menü ausklappen' : 'Menü einklappen'}>
              {collapsed ? <ChevronsRight size={16} /> : <><ChevronsLeft size={16} /><span className="text-[12px]">Einklappen</span></>}
            </button>
          </div>
        </aside>

        <div className="flex-1 min-w-0 flex flex-col">
          <header className="h-14 border-b bg-surface flex items-center gap-2 px-4 sticky top-0 z-20">
            <GlobalSearch />
            <div className="ml-auto flex items-center gap-1">
              <button className="btn-outline btn-sm h-8 hidden sm:inline-flex" onClick={() => setNewTaskFor(undefined)}><Plus size={14} />Aufgabe<span className="kbd ml-1 hidden lg:inline">n</span></button>
              <button className="btn-outline btn-sm h-8 hidden sm:inline-flex" onClick={() => setProjectDlg({ open: true, project: null })}><Plus size={14} />Projekt<span className="kbd ml-1 hidden lg:inline">p</span></button>
              <Notifications />
              <button className="btn-icon h-8 w-8" onClick={toggle} title={dark ? 'Heller Modus' : 'Dunkler Modus'}>{dark ? <Sun size={16} /> : <Moon size={16} />}</button>
              <span className="ml-1 w-8 h-8 rounded-full bg-raised border text-[11px] font-medium flex items-center justify-center" title={meta?.users.find((u) => u.id === meta.settings.my_user_id)?.name ?? ''}>
                {meta?.settings.my_user_code ?? '–'}
              </span>
            </div>
          </header>
          <main key={loc.pathname} className="flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
      </div>

      <TaskDialog task={task} onClose={() => setTask(null)} />
      <TaskForm open={newTaskFor !== false} onClose={() => setNewTaskFor(false)} projectId={newTaskFor === false ? undefined : newTaskFor} />
      <ProjectForm open={projectDlg.open} onClose={() => setProjectDlg({ open: false })} project={projectDlg.project} />
    </UiCtx.Provider>
  )
}

/* ------------------------------------------------------------------ Suche */
function GlobalSearch() {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const res = useSearch(q)
  const nav = useNavigate()
  const ui = useUi()
  const has = res.data && (res.data.projects.length + res.data.tasks.length + res.data.notes.length > 0)
  return (
    <div className="relative w-full max-w-md">
      <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint pointer-events-none" />
      <input id="global-search" className="input h-8 pl-8 bg-raised/60" placeholder="Suchen … Projektnummer, Name, Auftraggeber, Aufgabe" value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true) }} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => { if (e.key === 'Escape') { setQ(''); (e.target as HTMLInputElement).blur() } }} />
      {open && q.trim().length >= 2 && (
        <div className="absolute left-0 right-0 top-10 card shadow-pop max-h-[70vh] overflow-y-auto z-30 text-[13px]">
          {!has && <div className="px-3 py-3 text-muted">{res.isFetching ? 'Suche …' : 'Kein Treffer.'}</div>}
          {res.data && res.data.projects.length > 0 && (
            <div className="py-1">
              <div className="px-3 py-1 text-[11px] text-faint">Projekte</div>
              {res.data.projects.map((p) => (
                <button key={p.id} className="w-full text-left px-3 py-1.5 row-hover flex items-center gap-2" onMouseDown={() => { nav(`/projekte/${p.id}`); setQ('') }}>
                  <Dot className={{ rot: 'bg-rot', gelb: 'bg-gelb', gruen: 'bg-gruen', grau: 'bg-faint', fertig: 'bg-line' }[p.signal]} />
                  <span className="font-medium">{p.project_number}</span><span className="truncate text-muted">{p.name}</span>
                </button>
              ))}
            </div>
          )}
          {res.data && res.data.tasks.length > 0 && (
            <div className="py-1 border-t">
              <div className="px-3 py-1 text-[11px] text-faint">Aufgaben</div>
              {res.data.tasks.map((t) => (
                <button key={t.id} className="w-full text-left px-3 py-1.5 row-hover flex items-center gap-2" onMouseDown={() => { ui.openTask(t); setQ('') }}>
                  <span className={cx('truncate', t.status === 'erledigt' && 'line-through text-faint')}>{t.title}</span>
                  <span className="text-muted shrink-0">{t.project_number}</span>
                  <span className={cx('ml-auto shrink-0 text-[12px]', dueColor(t.due_state))}>{dueLabel(t)}</span>
                </button>
              ))}
            </div>
          )}
          {res.data && res.data.notes.length > 0 && (
            <div className="py-1 border-t">
              <div className="px-3 py-1 text-[11px] text-faint">Notizen</div>
              {res.data.notes.map((n) => (
                <button key={n.id} className="w-full text-left px-3 py-1.5 row-hover" onMouseDown={() => { nav(`/projekte/${n.project_id}`); setQ('') }}>
                  <span className="text-muted">{n.project_number} · {fmtDateTime(n.created_at)}</span>
                  <div className="truncate">{n.content}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ----------------------------------------------------------- Mitteilungen */
function Notifications() {
  const [open, setOpen] = useState(false)
  const notif = useNotifications().data ?? []
  const nav = useNavigate()
  const n = notif.filter((x) => x.level === 'rot' || x.level === 'orange').length
  return (
    <div className="relative">
      <button className="btn-icon h-8 w-8 relative" onClick={() => setOpen((o) => !o)} title="Hinweise" aria-label="Hinweise">
        <Bell size={16} />
        {n > 0 && <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-rot text-white text-[10px] font-medium flex items-center justify-center">{n}</span>}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-10 w-[360px] card shadow-pop z-30 max-h-[70vh] overflow-y-auto">
            <div className="px-3 py-2 border-b text-[12px] text-muted">{notif.length ? `${notif.length} Hinweise – berechnet aus Fristen und Status` : 'Nichts offen. Alles im Plan.'}</div>
            {notif.map((x, i) => (
              <button key={i} className="w-full text-left px-3 py-2 row-hover flex gap-2 items-start text-[13px] border-b last:border-0"
                onClick={() => { setOpen(false); if (x.project_id) nav(`/projekte/${x.project_id}`) }}>
                <Dot className={cx('mt-1.5', levelBg(x.level))} />
                <span>{x.text}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export function PageHeader({ title, sub, children }: { title: ReactNode; sub?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-4 mb-3 flex-wrap">
      <div>
        <h1 className="h1">{title}</h1>
        {sub && <p className="text-muted mt-0.5 text-[13px]">{sub}</p>}
      </div>
      {children && <div className="flex items-center gap-2 flex-wrap">{children}</div>}
    </div>
  )
}
