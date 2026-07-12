import { FileDiff, FileText, FlaskConical, Gauge, MessageSquare, Settings, SlidersHorizontal } from 'lucide-react'

const SIDEBAR_ITEMS = [
  { id: 'home', icon: Gauge, label: 'Overview' },
  { id: 'system', icon: FileText, label: 'System design' },
  { id: 'policy', icon: SlidersHorizontal, label: 'Trim policy' },
  { id: 'diff', icon: FileDiff, label: 'Diff review' },
  { id: 'demo', icon: FlaskConical, label: 'Live test' },
  { id: 'sessions', icon: MessageSquare, label: 'Conversations' },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar({ active, onNavigate }) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <button className="brand-mini" aria-label="TrimPy home" title="TrimPy home" onClick={() => onNavigate('home')}>
        <span className="brand-mini-top" />
        <span className="brand-mini-stem" />
      </button>
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
