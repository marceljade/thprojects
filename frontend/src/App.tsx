import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { Shell } from '@/components/layout/Shell'
import { ToastProvider } from '@/components/ui'
import Dashboard from '@/pages/Dashboard'
import Tasks from '@/pages/Tasks'
import Projects from '@/pages/Projects'
import ProjectDetail from '@/pages/ProjectDetail'
import Calendar from '@/pages/Calendar'
import Schedule from '@/pages/Schedule'
import ActivityPage from '@/pages/ActivityPage'
import Settings from '@/pages/Settings'

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: true } } })

const router = createBrowserRouter([
  {
    path: '/', element: <Shell />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'aufgaben', element: <Tasks /> },
      { path: 'projekte', element: <Projects /> },
      { path: 'projekte/:id', element: <ProjectDetail /> },
      { path: 'kalender', element: <Calendar /> },
      { path: 'zeitplan', element: <Schedule /> },
      { path: 'aktivitaeten', element: <ActivityPage /> },
      { path: 'einstellungen', element: <Settings /> },
      { path: '*', element: <div className="page text-muted">Diese Seite gibt es nicht.</div> },
    ],
  },
])

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>
  )
}
