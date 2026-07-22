import { Bell, BookOpen, Check, ChevronLeft, ChevronRight, CircleHelp, FileDiff, FlaskConical, Gauge, GitBranch, MessageSquare, Moon, Settings, ShieldCheck, SlidersHorizontal, Sun } from 'lucide-react'
import { useState } from 'react'
import { PALETTES } from '../theme.js'

const SIDEBAR_ITEMS = [
  { section: 'Overview' },
  { id: 'home', icon: Gauge, label: 'Dashboard' },
  { section: 'Data' },
  { id: 'activity', icon: GitBranch, label: 'Repositories' },
  { id: 'policy', icon: SlidersHorizontal, label: 'Trim policy' },
  { id: 'system', icon: BookOpen, label: 'Developer docs' },
  { section: 'Insights' },
  { id: 'sessions', icon: MessageSquare, label: 'Conversations' },
  { id: 'demo', icon: FlaskConical, label: 'A/B preflight' },
  { id: 'validation', icon: ShieldCheck, label: 'Validation' },
  { section: 'Admin' },
  { id: 'diff', icon: FileDiff, label: 'Diff review' },
  { id: 'alerts', icon: Bell, label: 'Alerts' },
  { id: 'feedback', icon: CircleHelp, label: 'Help & feedback' },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar({ active, onNavigate, collapsed, onToggle, darkMode, onToggleDarkMode, palette, savedPalette, isPreviewing, onPreviewTheme, onSaveTheme, onCancelPreview, optimizerEnabled = true }) {
  const [brandClicks, setBrandClicks] = useState(0)
  const [secretOpen, setSecretOpen] = useState(false)
  const [themeMenuOpen, setThemeMenuOpen] = useState(false)

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
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${optimizerEnabled ? 'optimizer-on' : 'optimizer-off'}`} aria-label="Primary navigation">
      <div className="sidebar-top-row">
        <button className="brand-mini" aria-label="TrimPy home" title="TrimPy home" onClick={activateBrand}>
          <span className="brand-mini-mark"><span className="brand-mini-letter">T</span><span className="brand-reduction-glyph" aria-hidden="true"><i /><i /><i /><b /></span><span className="brand-status-dot" aria-hidden="true" /></span>
          <span className="brand-mini-wordmark"><span className="brand-mini-name">TrimPy</span><span className="brand-mini-tagline">token reducer</span></span>
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
        <div className="theme-picker">
          {themeMenuOpen && (
            <button
              className="theme-picker-backdrop"
              aria-label="Close theme picker"
              onClick={() => { onCancelPreview?.(); setThemeMenuOpen(false) }}
            />
          )}
          <button className="theme-toggle" onClick={() => setThemeMenuOpen(value => !value)} aria-label="Choose theme" title="Choose theme" aria-expanded={themeMenuOpen}>
            <span className="theme-toggle-icon">{darkMode ? <Moon size={17} /> : <Sun size={17} />}</span>
            <span>{PALETTES.find(item => item.id === palette)?.label || (darkMode ? 'Dark' : 'Light')}</span>
          </button>
          {themeMenuOpen && (
            <div className="theme-picker-menu" role="menu">
              {isPreviewing && (
                <div className="theme-picker-preview-bar">
                  <span>Previewing <b>{PALETTES.find(item => item.id === palette)?.label}</b></span>
                  <div>
                    <button type="button" className="theme-picker-cancel" onClick={onCancelPreview}>Cancel</button>
                    <button type="button" className="theme-picker-save" onClick={() => { onSaveTheme?.(); setThemeMenuOpen(false) }}>Save</button>
                  </div>
                </div>
              )}
              <button className="theme-picker-quick-switch" onClick={() => { onToggleDarkMode?.(); setThemeMenuOpen(false) }}>
                {darkMode ? <Sun size={14} /> : <Moon size={14} />}
                <span>Switch to {darkMode ? 'light' : 'dark'}</span>
              </button>
              {['dark', 'light'].map(family => (
                <div className="theme-picker-group" key={family}>
                  <small>{family === 'dark' ? 'Dark' : 'Light'}</small>
                  <div className="theme-picker-options">
                    {PALETTES.filter(item => item.family === family).map(item => (
                      <button
                        key={item.id}
                        className={`theme-picker-option ${palette === item.id ? 'active' : ''} ${savedPalette === item.id ? 'is-saved' : ''}`}
                        onClick={() => onPreviewTheme?.(item.id)}
                        title={item.note}
                      >
                        <span className="theme-picker-swatch">{item.swatch.map((color, index) => <i key={index} style={{ background: color }} />)}</span>
                        <span>{item.label}</span>
                        {palette === item.id && <Check size={12} />}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
