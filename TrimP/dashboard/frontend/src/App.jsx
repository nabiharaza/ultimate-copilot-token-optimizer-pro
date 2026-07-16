import { lazy, Suspense, useState, useEffect } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Config from './pages/Config.jsx'
import Repositories from './pages/Repositories.jsx'
import OverviewDashboard from './pages/OverviewDashboard.jsx'
import SystemDesign from './pages/SystemDesign.jsx'
import TrimPolicy from './pages/TrimPolicy.jsx'
import DiffReview from './pages/DiffReview.jsx'
import Feedback from './pages/Feedback.jsx'
import LiveTest from './pages/LiveTest.jsx'
import Alerts from './pages/Alerts.jsx'
import ValidationCenter from './pages/ValidationCenter.jsx'
import DarkModePrototypes from './pages/DarkModePrototypes.jsx'
import { REFRESH_EVENT } from './hooks/useApi.js'
import { useTrimPEnabled } from './components/TrimPSwitch.jsx'
import { Loading } from './components/Charts.jsx'

const Sessions = lazy(() => import('./pages/Sessions.jsx'))

export default function App() {
  if (new URLSearchParams(window.location.search).has('dark-prototypes')) return <DarkModePrototypes />
  // Persistent page state (survives refresh)
  const [page, setPage] = useState(() => {
    return localStorage.getItem('TrimP_current_page') || 'home'
  })
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('TrimP_sidebar_collapsed') === 'true')
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('TrimP_theme') !== 'light')
  const { enabled: optimizerEnabled } = useTrimPEnabled()

  // Save page to localStorage on change
  useEffect(() => {
    localStorage.setItem('TrimP_current_page', page)
  }, [page])

  useEffect(() => {
    localStorage.setItem('TrimP_sidebar_collapsed', String(sidebarCollapsed))
  }, [sidebarCollapsed])

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? 'dark' : 'light'
    localStorage.setItem('TrimP_theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'hidden') {
        window.dispatchEvent(new CustomEvent(REFRESH_EVENT, { detail: { at: Date.now() } }))
      }
    }, 1000)
    return () => window.clearInterval(timer)
  }, [])

  const pages = { 
    home: OverviewDashboard,
    optimize: OverviewDashboard,
    system: SystemDesign,
    policy: TrimPolicy,
    diff: DiffReview,
    demo: LiveTest,
    validation: ValidationCenter,
    activity: Repositories,
    sessions: Sessions,
    settings: Config,
    feedback: Feedback,
    alerts: Alerts,
  }
  
  const Page = pages[page] || OverviewDashboard

  return (
    <div className={`app-shell ${darkMode ? 'theme-dark' : 'theme-light'} ${sidebarCollapsed ? 'is-sidebar-collapsed' : ''}`}>
      <Sidebar active={page} onNavigate={setPage} collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(value => !value)} darkMode={darkMode} onToggleDarkMode={() => setDarkMode(value => !value)} optimizerEnabled={optimizerEnabled} />
      <div className="main-content" style={{ flex: 1, overflowY: 'auto' }}>
        <Suspense fallback={<Loading />}>
          <Page onNavigate={setPage} darkMode={darkMode} />
        </Suspense>
      </div>
    </div>
  )
}
