import { Activity, Bell, ChevronLeft, ChevronRight, FileDiff, FileText, FlaskConical, Gauge, GitBranch, MessageSquare, Settings, SlidersHorizontal } from 'lucide-react'

const SIDEBAR_ITEMS = [
  { id: 'home', icon: Gauge, label: 'Overview' },
  { id: 'diff', icon: FileDiff, label: 'Diff review' },
  { id: 'policy', icon: SlidersHorizontal, label: 'Trim policy' },
  { id: 'activity', icon: GitBranch, label: 'Repos' },
  { id: 'sessions', icon: MessageSquare, label: 'Conversations' },
  { id: 'live', icon: Activity, label: 'Live activity' },
  { id: 'demo', icon: FlaskConical, label: 'Live test' },
  { id: 'system', icon: FileText, label: 'System design' },
  { id: 'alerts', icon: Bell, label: 'Alerts' },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar({ active, onNavigate, collapsed, onToggle }) {
  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`} aria-label="Primary navigation">
      <div className="sidebar-top-row">
        <button className="brand-mini" aria-label="TrimPy home" title="TrimPy home" onClick={() => onNavigate('home')}>
          <span className="brand-mini-top" />
          <span className="brand-mini-stem" />
          <span className="brand-mini-name">TrimPy</span>
        </button>
        <button className="sidebar-collapse" onClick={onToggle} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'} title={collapsed ? 'Expand navigation' : 'Collapse navigation'}>
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
      <nav className="side-nav">
        {SIDEBAR_ITEMS.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            className={`nav-button ${active === id ? 'active' : ''}`}
            data-tooltip={label}
            aria-label={label}
            onClick={() => onNavigate(id)}
          >
            <Icon size={21} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div className="avatar" aria-label="Trim-Pilot operator">
          TP
          <span className="avatar-dot" />
        </div>
      </div>
    </aside>
  )
}
