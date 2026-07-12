import { Activity, Bell, ChevronLeft, ChevronRight, CircleHelp, FileDiff, FileText, FlaskConical, Gauge, GitBranch, MessageSquare, Settings, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'

const SIDEBAR_ITEMS = [
  { section: 'Overview' },
  { id: 'home', icon: Gauge, label: 'Dashboard' },
  { section: 'Data' },
  { id: 'activity', icon: GitBranch, label: 'Repositories' },
  { id: 'policy', icon: SlidersHorizontal, label: 'Trim policy' },
  { id: 'system', icon: FileText, label: 'Connections' },
  { section: 'Insights' },
  { id: 'sessions', icon: MessageSquare, label: 'Conversations' },
  { id: 'live', icon: Activity, label: 'Live activity' },
  { id: 'demo', icon: FlaskConical, label: 'Experiments' },
  { id: 'validation', icon: ShieldCheck, label: 'Validation' },
  { section: 'Admin' },
  { id: 'diff', icon: FileDiff, label: 'Diff review' },
  { id: 'alerts', icon: Bell, label: 'Alerts' },
  { id: 'feedback', icon: CircleHelp, label: 'Help & feedback' },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar({ active, onNavigate, collapsed, onToggle }) {
  const [brandClicks, setBrandClicks] = useState(0)
  const [secretOpen, setSecretOpen] = useState(false)

  function activateBrand() {
    onNavigate('home')
    const next = brandClicks + 1
    setBrandClicks(next)
    if (next >= 3) {
      setSecretOpen(true)
      setBrandClicks(0)
      window.setTimeout(() => setSecretOpen(false), 4200)
    }
  }

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`} aria-label="Primary navigation">
      <div className="sidebar-top-row">
        <button className="brand-mini" aria-label="TrimPy home" title="TrimPy home" onClick={activateBrand}>
          <span className="brand-mini-mark"><span className="brand-mini-top" /><span className="brand-mini-stem" /></span>
          <span className="brand-mini-wordmark"><span className="brand-mini-name">TrimPy</span><span className="brand-mini-tagline">Cut tokens. Keep context.</span></span>
        </button>
        <button className="sidebar-collapse" onClick={onToggle} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'} title={collapsed ? 'Expand navigation' : 'Collapse navigation'}>
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
      <nav className="side-nav">
        {SIDEBAR_ITEMS.map((item, index) => {
          if (item.section) return <div className="nav-section-label" key={`${item.section}-${index}`}>{item.section}</div>
          const { id, icon: Icon, label } = item
          return <button key={id} className={`nav-button ${active === id ? 'active' : ''}`} data-tooltip={label} aria-label={label} onClick={() => onNavigate(id)}>
            <Icon size={21} /><span>{label}</span>
          </button>
        })}
      </nav>
      {secretOpen && <div className="sidebar-secret" role="status"><b>TrimPy unlocked</b><span>Cut the noise. Keep the signal.</span></div>}
      <div className="sidebar-footer">
        <div className="avatar" aria-label="Trim-Pilot operator">
          TP
          <span className="avatar-dot" />
        </div>
      </div>
    </aside>
  )
}
