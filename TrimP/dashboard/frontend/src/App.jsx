import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar.jsx'
import HomeNew from './pages/HomeNew.jsx'
import CompressionLive from './pages/CompressionLive.jsx'
import Savings from './pages/Savings.jsx'
import Config from './pages/Config.jsx'
import Repositories from './pages/Repositories.jsx'
import Sessions from './pages/Sessions.jsx'
import CopilotOptimizer from './pages/CopilotOptimizer.jsx'
import SystemDesign from './pages/SystemDesign.jsx'
import TrimPolicy from './pages/TrimPolicy.jsx'
import DiffReview from './pages/DiffReview.jsx'
import Feedback from './pages/Feedback.jsx'
import LiveTest from './pages/LiveTest.jsx'

export default function App() {
  // Persistent page state (survives refresh)
  const [page, setPage] = useState(() => {
    return localStorage.getItem('TrimP_current_page') || 'home'
  })

  // Save page to localStorage on change
  useEffect(() => {
    localStorage.setItem('TrimP_current_page', page)
  }, [page])

  const pages = { 
    home: CopilotOptimizer, 
    optimize: CopilotOptimizer,
    system: SystemDesign,
    policy: TrimPolicy,
    diff: DiffReview,
    demo: LiveTest,
    activity: Repositories,
    sessions: Sessions,
    savings: Savings, 
    settings: Config,
    feedback: Feedback,
  }
  
  const Page = pages[page] || HomeNew

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>
      <Sidebar active={page} onNavigate={setPage} />
      <div className="main-content" style={{ flex: 1, overflowY: 'auto' }}>
        <Page onNavigate={setPage} />
      </div>
    </div>
  )
}
