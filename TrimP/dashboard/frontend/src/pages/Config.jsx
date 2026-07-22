import { useEffect, useMemo, useState } from 'react'
import {
  Activity, Archive, ArchiveRestore, Braces, Check, CheckCircle2, ChevronDown, CircleHelp,
  Clock3, Code2, Database, Download, ExternalLink, FileArchive, FileCode2, FileJson,
  Gauge, GitBranch, Globe2, HardDrive, Info, LockKeyhole, Palette, RefreshCw, Save, Search,
  Server, Settings2, ShieldCheck, SlidersHorizontal, Sparkles, Tag, Terminal, Trash2,
  WalletCards, X, XCircle, Zap,
} from 'lucide-react'
import { useApi, useRefreshTick } from '../hooks/useApi.js'
import { Loading } from '../components/Charts.jsx'
import { FONT_SIZES, PALETTES } from '../theme.js'

const FEATURE_META = {
  'compression.bash.enabled': ['Bash/script content', 'Terminal output', 'Compresses command output while preserving errors and exit context.', Terminal],
  'compression.search.enabled': ['Search results', 'Search results', 'Removes repeated and low-signal search lines.', Search],
  'compression.json.enabled': ['JSON content', 'JSON content', 'Minimizes safe JSON without changing its structure.', FileJson],
  'compression.delta.enabled': ['Delta / changes', 'Deltas/changes', 'Collapses repeated diff context around the active change.', GitBranch],
  'compression.skeleton.enabled': ['Code skeleton', 'Code selections', 'Keeps signatures and structure while trimming implementation noise.', Code2],
  'compression.archive.enabled': ['Archive content', 'Archives & bundles', 'Summarizes large archives and bundled artifacts before forwarding.', Archive],
  'compression.verbosity.enabled': ['Verbose output', 'Verbose outputs', 'Removes repeated status and progress chatter from tool output.', Activity],
  'compression.structural.enabled': ['Structural normalization', 'Structural normalization', 'Normalizes safe nested payload structure before token estimation.', Braces],
  'compression.loop_detect.enabled': ['Loop detection', 'Loop detection', 'Stops repeated tool and retry output from inflating the next request.', RefreshCw],
  'compression.activity.enabled': ['Activity context', 'Activity & workflow', 'Preserves the active workflow while dropping stale activity history.', Zap],
  'compression.enabled': ['TrimPy optimization', 'Enable compression', 'Master switch for request shaping and token accounting.', SlidersHorizontal],
  'compression.policy': ['Compression policy', 'Compression policy', 'Select the default balance between reduction and context fidelity.', SlidersHorizontal],
}

const PRICING = [
  ['pricing.haiku_per_1m', 'Haiku', 'Claude Haiku', Sparkles, 'purple'],
  ['pricing.sonnet_per_1m', 'Sonnet', 'Claude Sonnet', Zap, 'orange'],
  ['pricing.opus_per_1m', 'Opus', 'Claude Opus', Globe2, 'cyan'],
  ['pricing.gpt4_per_1m', 'GPT-4', 'GPT-4', LockKeyhole, 'slate'],
]

const ADVANCED_KEYS = ['quality.min_grade', 'proxy.port', 'proxy.upstream', 'proxy.azure_endpoint', 'session.copilot_db_path']

function serviceStatus(health, name) {
  return (health?.services || []).find(service => service.name === name)
}

function displayValue(value) {
  return value === undefined || value === null || value === '' ? '—' : String(value)
}

function shortTime(value) {
  if (!value) return 'No traffic yet'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function Config({ onNavigate, palette, savedPalette, isPreviewing, onPreviewTheme, onSaveTheme, onCancelPreview, fontSize, onSetFontSize }) {
  const { data: config, loading, refetch } = useApi('/api/config')
  const [saving, setSaving] = useState(null)
  const [editValues, setEditValues] = useState({})
  const [clearOpen, setClearOpen] = useState(false)
  const [confirmation, setConfirmation] = useState('')
  const [clearState, setClearState] = useState(null)
  const [health, setHealth] = useState(null)
  const [saveMessage, setSaveMessage] = useState('')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState(() => new Set())
  const refreshTick = useRefreshTick()

  async function loadHealth() {
    const response = await fetch('/api/live-health')
    if (response.ok) setHealth(await response.json())
  }

  useEffect(() => { loadHealth() }, [refreshTick])

  const compressionEntries = Object.keys(FEATURE_META).filter(key => key.startsWith('compression.'))
  const visibleCompression = useMemo(() => compressionEntries.filter(key => {
    const [title, subtitle, description] = FEATURE_META[key]
    const query = search.trim().toLowerCase()
    return !query || `${key} ${title} ${subtitle} ${description}`.toLowerCase().includes(query)
  }), [config, search])

  if (loading && !config) return <Loading />

  function staged(key) {
    return editValues[key] ?? config?.[key] ?? (key === 'compression.policy' ? 'balanced' : '')
  }

  function update(key, value) {
    setEditValues(current => ({ ...current, [key]: String(value) }))
    setSaveMessage('')
  }

  async function save(key, value) {
    setSaving(key)
    try {
      const response = await fetch(`/api/config/${key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail || 'Could not save setting')
      if (key === 'logs.retention_months') {
        const deleted = result.pruned?.deleted ?? 0
        setSaveMessage(`Retention saved. ${deleted.toLocaleString()} expired record${deleted === 1 ? '' : 's'} removed.`)
      }
      setEditValues(current => { const next = { ...current }; delete next[key]; return next })
      await refetch()
      return true
    } catch (error) {
      setSaveMessage(error.message)
      return false
    } finally {
      setSaving(null)
    }
  }

  async function saveAll() {
    const pending = Object.entries(editValues)
    if (!pending.length) {
      setSaveMessage('Everything is already saved.')
      return
    }
    setSaving('all')
    let savedCount = 0
    for (const [key, value] of pending) {
      if (await save(key, value)) savedCount += 1
    }
    setSaving(null)
    setSaveMessage(`${savedCount} setting${savedCount === 1 ? '' : 's'} saved.`)
  }

  async function clearDatabase() {
    if (confirmation !== 'CLEAR DB') return
    setClearState('clearing')
    const response = await fetch('/api/database/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmation }),
    })
    const result = await response.json()
    if (result.ok) {
      setClearState('cleared')
      setConfirmation('')
      setTimeout(() => { setClearOpen(false); setClearState(null); refetch() }, 900)
    } else setClearState('error')
  }

  const retentionValue = editValues['logs.retention_months'] ?? config?.['logs.retention_months'] ?? '6'
  const allExpanded = visibleCompression.length > 0 && visibleCompression.every(key => expanded.has(key))
  const byok = serviceStatus(health, 'BYOK proxy')
  const ide = serviceStatus(health, 'IDE HTTPS proxy')
  const services = [
    { label: 'BYOK proxy', detail: byok?.detail || 'Waiting for health check', status: byok?.status || 'down', icon: Server },
    { label: 'IDE bridge', detail: ide?.detail || 'Waiting for health check', status: ide?.status || 'down', icon: GitBranch },
    { label: 'IDE HTTPS bridge', detail: ide?.detail || 'Waiting for health check', status: ide?.status || 'down', icon: LockKeyhole },
  ]
  const editorProbes = health?.editor_probes || []

  function toggleExpand(key) {
    setExpanded(current => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function toggleAll() {
    setExpanded(allExpanded ? new Set() : new Set(visibleCompression))
  }

  return (
    <main className="settings-page">
      <header className="settings-page-header">
        <div>
          <div className="settings-page-kicker"><Settings2 size={14} /> Administration</div>
          <h1>Settings</h1>
          <p>Configure your TrimPy environment and system behavior.</p>
        </div>
        <div className="settings-header-actions">
          <label className="settings-search"><Search size={15} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search settings…" aria-label="Search settings" /><kbd>⌘ K</kbd></label>
          <span className="settings-environment"><i /> Production</span>
          <button className="settings-save-all" onClick={saveAll} disabled={saving === 'all'}><Check size={15} /> {saving === 'all' ? 'Saving…' : 'Save changes'}</button>
        </div>
      </header>

      <section className="settings-top-grid">
        <article className="settings-health-panel settings-card">
          <div className="settings-section-heading"><div><h2><Activity size={16} /> Live service health</h2><p>Automatic checks for every TrimPy dependency and IDE bridge.</p></div><button className="icon-button" onClick={loadHealth} title="Refresh health"><RefreshCw size={16} /></button></div>
          <div className="settings-service-grid">{services.map(service => { const Icon = service.icon; const up = service.status === 'up'; return <div className={`settings-service-card ${up ? 'up' : 'down'}`} key={service.label}><div className="settings-service-name"><span>{up ? <CheckCircle2 size={15} /> : <XCircle size={15} />} </span><b>{service.label}</b></div><small>{service.detail}</small><em><i /> {up ? 'Working in real time' : 'Needs attention'}</em></div> })}</div>
          <div className="settings-ide-health">{(health?.configured_ides || []).map(ideItem => <span key={ideItem.product}><i />{ideItem.product} <b>•</b> {ideItem.host}:{ideItem.port}</span>)}{(!health || health.configured_ides?.length === 0) && <span>No IDE integrations configured</span>}</div>
          <div className="settings-probe-grid">{editorProbes.map(probe => { const ok = !!probe.intercepted; const signal = probe.signal || {}; const last = signal.last_logged_at || signal.last_intercept_at || signal.last_probe_at; return <div className={`settings-probe-card ${ok ? 'up' : 'down'}`} key={probe.editor}><span>{ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}</span><b>{String(probe.editor || 'editor').toUpperCase()}</b><small>{probe.request_source || probe.error || 'No probe response'}</small><em>{ok ? 'Intercepting' : 'Not intercepted'} · {shortTime(last)}</em></div> })}</div>
        </article>

        <article className="settings-release-card settings-card">
          <div className="settings-section-heading"><div><h2><Database size={16} /> Release metadata</h2></div></div>
          <div className="settings-release-hero"><strong>TrimPy v1.0.0</strong><span>Enterprise token optimization system</span><div><b>Version 1.0.0</b><b>Observability</b><b>GitHub Copilot Enterprise</b><b>Proxy</b></div></div>
          <div className="settings-release-copy"><b>Developer logs and release notes</b><p>TrimPy captures request lifecycle, repository and IDE attribution, compression decisions, token usage, response metadata, and service health. Release focus: traceability, safe context shaping, and measured cost reduction.</p></div>
        </article>

        <article className="settings-privacy-card settings-card">
          <div className="settings-section-heading"><div><h2><ShieldCheck size={16} /> Privacy & storage</h2></div></div>
          <b className="settings-card-title">Keep TrimPy logs</b>
          <p>Choose how long request traces, compression audits, savings history, and imported Copilot usage stay in this local workspace.</p>
          <small>Default: 6 months. Configuration is always preserved.</small>
          <label className="settings-field-label" htmlFor="retention-months">Retention period</label>
          <div className="settings-retention-controls"><select id="retention-months" value={retentionValue} onChange={event => update('logs.retention_months', event.target.value)}><option value="1">1 month</option><option value="3">3 months</option><option value="6">6 months (recommended)</option><option value="12">12 months</option><option value="24">24 months</option><option value="0">Forever</option></select><button className="retention-save" onClick={() => save('logs.retention_months', retentionValue)} disabled={saving === 'logs.retention_months'}><Save size={14} /> Save period</button></div>
          {saveMessage && <span className="settings-save-message">{saveMessage}</span>}
        </article>
      </section>

      <section className="settings-appearance settings-card">
        <div className="settings-section-heading"><div><h2><Palette size={16} /> Appearance</h2><p>Seven themes modeled on real editors — GitHub, VS Code, IntelliJ, Solarized, and PyCharm Darcula. Click one to preview it across the whole app, then save it or cancel.</p></div></div>
        {isPreviewing && (
          <div className="settings-preview-bar">
            <span>Previewing <b>{PALETTES.find(item => item.id === palette)?.label}</b> — this isn't saved yet.</span>
            <div>
              <button type="button" className="settings-preview-cancel" onClick={onCancelPreview}>Cancel</button>
              <button type="button" className="settings-preview-save" onClick={onSaveTheme}><Save size={13} /> Save theme</button>
            </div>
          </div>
        )}
        <div className="settings-palette-grid">
          {['dark', 'light'].map(family => (
            <div className="settings-palette-group" key={family}>
              <small className="settings-palette-group-label">{family === 'dark' ? 'Dark' : 'Light'}</small>
              <div className="settings-palette-options">
                {PALETTES.filter(item => item.family === family).map(item => (
                  <button
                    type="button"
                    key={item.id}
                    className={`settings-palette-option ${palette === item.id ? 'active' : ''} ${savedPalette === item.id ? 'is-saved' : ''}`}
                    onClick={() => onPreviewTheme?.(item.id)}
                    title={item.note}
                  >
                    <span className="settings-palette-swatch">{item.swatch.map((color, index) => <i key={index} style={{ background: color }} />)}</span>
                    <span className="settings-palette-name">{item.label}</span>
                    {savedPalette === item.id && !isPreviewing && <Check size={13} className="settings-palette-check" />}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="settings-font-size-row">
          <div><b>UI size</b><small>Scales fonts, icons, and spacing together across the whole app.</small></div>
          <div className="settings-font-size-options" role="group" aria-label="UI size">
            {FONT_SIZES.map(item => (
              <button
                type="button"
                key={item.id}
                className={`settings-font-size-option ${fontSize === item.id ? 'active' : ''}`}
                onClick={() => onSetFontSize?.(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="settings-danger-zone settings-card"><div><div className="settings-danger-title"><Trash2 size={17} /> Telemetry database</div><p>Remove captured conversations, traces, quality scores, and savings history. Configuration is preserved.</p></div><button className="danger-button" onClick={() => setClearOpen(true)}><Trash2 size={15} /> Clear DB</button></section>

      <section className="settings-features-card settings-card">
        <div className="settings-section-heading"><div><h2><SlidersHorizontal size={16} /> Compression Features</h2><p>Control how TrimPy compresses and optimizes context before it is sent to models.</p></div><button className="settings-expand-all" onClick={toggleAll}><ChevronDown size={15} /> {allExpanded ? 'Collapse all' : 'Expand all'}</button></div>
        <div className="settings-feature-grid">{visibleCompression.map(key => { const [title, subtitle, description, Icon] = FEATURE_META[key]; const enabled = staged(key) === 'true'; return <div className={`settings-feature-row ${expanded.has(key) ? 'is-expanded' : ''}`} key={key}><span className="settings-feature-icon"><Icon size={15} /></span><div className="settings-feature-copy"><b>{key}</b><small>{subtitle}</small>{expanded.has(key) && <p>{description}</p>}</div>{key === 'compression.policy' ? <select value={staged(key)} onChange={event => update(key, event.target.value)}><option value="conservative">conservative</option><option value="balanced">balanced</option><option value="aggressive">aggressive</option></select> : <button className={`settings-toggle ${enabled ? 'on' : ''}`} role="switch" aria-checked={enabled} aria-label={`${enabled ? 'Disable' : 'Enable'} ${title}`} onClick={() => update(key, enabled ? 'false' : 'true')}><i /></button>}<button className="settings-row-expand" onClick={() => toggleExpand(key)} aria-label={`Show details for ${title}`}><ChevronDown size={14} /></button></div> })}</div>
      </section>

      <section className="settings-bottom-grid">
        <article className="settings-card settings-pricing-card"><div className="settings-section-heading"><div><h2><Tag size={16} /> Pricing ($ / 1M tokens)</h2><p>Set the per-1M token pricing used for cost estimation.</p></div></div>{PRICING.map(([key, label, model, Icon, tone]) => <label className="settings-pricing-row" key={key}><span className={`settings-pricing-icon ${tone}`}><Icon size={14} /></span><b title={model}>{label}</b><input value={staged(key)} onChange={event => update(key, event.target.value)} aria-label={`${model} price per 1M tokens`} /></label>)}</article>
        <article className="settings-card settings-dashboard-card"><div className="settings-section-heading"><div><h2><Gauge size={16} /> Dashboard</h2><p>Configure local dashboard behavior.</p></div></div><div className="settings-inline-fields"><label><b>dashboard.web_port</b><small>Port for the TrimPy dashboard</small></label><input value={staged('dashboard.web.port')} onChange={event => update('dashboard.web.port', event.target.value)} /></div><div className="settings-inline-fields"><label><b>dashboard.web_auto_open</b><small>Open dashboard automatically</small></label><button className={`settings-toggle ${staged('dashboard.web.auto_open') === 'true' ? 'on' : ''}`} role="switch" aria-checked={staged('dashboard.web.auto_open') === 'true'} onClick={() => update('dashboard.web.auto_open', staged('dashboard.web.auto_open') === 'true' ? 'false' : 'true')}><i /></button></div></article>
        <article className="settings-card settings-archive-card"><div className="settings-section-heading"><div><h2><ArchiveRestore size={16} /> Archive</h2><p>Archive and export configuration.</p></div></div><div className="settings-archive-box"><span className="settings-archive-icon"><Download size={17} /></span><div><b>Archive settings and telemetry (export)</b><small>Download a snapshot of your configuration and telemetry for backup or migration.</small></div><button className="settings-outline-action" onClick={() => setSaveMessage('Archive export is available from the local database tooling.')}>Create archive</button></div><label className="settings-archive-threshold"><span>Archive threshold (characters)</span><input value={staged('archive.threshold_chars')} onChange={event => update('archive.threshold_chars', event.target.value)} /></label></article>
      </section>

      <details className="settings-advanced-card settings-card"><summary><FileCode2 size={16} /><span><b>Advanced configuration</b><small>Proxy, quality, session database, and other low-level controls.</small></span><ChevronDown size={16} /></summary><div className="settings-advanced-grid">{ADVANCED_KEYS.map(key => <label key={key}><b>{key}</b><input value={staged(key)} onChange={event => update(key, event.target.value)} /></label>)}</div></details>
      <footer className="settings-footer"><LockKeyhole size={16} /><span>All settings are stored securely on your machine and never leave your environment.</span><a href="#system" onClick={event => { event.preventDefault(); onNavigate?.('system') }}>View documentation <ExternalLink size={13} /></a></footer>

      {clearOpen && <div className="confirm-backdrop" role="dialog" aria-modal="true" aria-label="Clear database confirmation"><section className="confirm-dialog"><button className="confirm-close" onClick={() => setClearOpen(false)} title="Close"><X size={17} /></button><div className="confirm-icon"><Info size={22} /></div><h2>Clear DB?</h2><p>This permanently deletes all captured conversations, traces, quality scores, and savings data. This cannot be undone.</p><label>Type <strong>CLEAR DB</strong> to confirm</label><input autoFocus value={confirmation} onChange={event => setConfirmation(event.target.value)} placeholder="CLEAR DB" /><div className="confirm-actions"><button className="secondary-button" onClick={() => setClearOpen(false)}>Cancel</button><button className="danger-button" disabled={confirmation !== 'CLEAR DB' || clearState === 'clearing'} onClick={clearDatabase}>{clearState === 'clearing' ? 'Clearing…' : clearState === 'cleared' ? 'Cleared' : 'Clear DB'}</button></div></section></div>}
    </main>
  )
}
