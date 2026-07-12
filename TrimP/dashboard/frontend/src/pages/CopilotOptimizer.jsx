import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  ArrowUpRight,
  Boxes,
  CheckCircle2,
  Clock,
  DollarSign,
  GitBranch,
  GitFork,
  Layers,
  Monitor,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Search,
  MessageSquare,
  MoreHorizontal,
  Server,
  Sparkles,
  Zap,
  XCircle,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const RANGE_OPTIONS = [
  ['hour', '1H'],
  ['day', '24H'],
  ['week', '7D'],
  ['month', '30D'],
  ['quarter', '3M'],
  ['year', '1Y'],
  ['all', 'All'],
]

const GRANULARITY_OPTIONS = [
  ['auto', 'Auto'],
  ['minute', 'Minute'],
  ['hour', 'Hour'],
  ['day', 'Day'],
  ['week', 'Week'],
  ['month', 'Month'],
  ['year', 'Year'],
]

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

function formatDollars(value) {
  return `$${Number(value || 0).toFixed(4)}`
}

function parseStoredDate(value) {
  if (!value) return null
  const text = String(value)
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(text) ? text : `${text}Z`)
}

function formatDateTime(iso) {
  if (!iso) return '—'
  const date = parseStoredDate(iso)
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString([], {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  })
}

function formatTime(iso) {
  if (!iso) return '—'
  const date = parseStoredDate(iso)
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  })
}

function ideName(source) {
  const value = String(source || '').toLowerCase()
  if (value.includes('pycharm')) return 'PyCharm'
  if (value.includes('rider')) return 'Rider'
  if (value.includes('vscode')) return 'VS Code'
  if (value.includes('cli')) return 'Copilot CLI'
  return 'Unknown client'
}

function healthFix(service) {
  if (service.name === 'BYOK proxy') return 'Start python3 byok_server.py --port 8766.'
  if (service.name === 'IDE HTTPS proxy') return 'Start the JetBrains bridge on port 8767 and verify its certificate.'
  return 'Restart the integration and verify its proxy settings.'
}

function compressionExplain(method) {
  const value = String(method || '').toLowerCase()
  if (value.includes('tool')) return 'Tool output compaction keeps errors, commands, and high-signal lines while removing repetitive noise.'
  if (value.includes('json')) return 'JSON shaping reduces repeated keys and low-value rows while preserving structured data.'
  if (value.includes('bash') || value.includes('search')) return 'Command/search shaping keeps matches, failures, and relevant file context.'
  if (value.includes('lingua') || value.includes('prompt')) return 'Prompt compression removes redundant connective text while preserving intent and constraints.'
  return 'TrimP selected the safest compressor for this field based on its content type.'
}

const TRIMPY_SECRETS = [
  'A little TrimPy secret: every token we cut leaves a trace.',
  'Context is the chorus. TrimPy keeps the part that moves the work forward.',
  'The best request is not the smallest one. It is the one with no wasted words.',
  'TrimPy says: make room for the useful bits.',
]

function pct(value) {
  return `${Number(value || 0).toFixed(2)}%`
}

function activitySparkHeights(items) {
  const points = (items || []).slice().reverse().slice(-34)
  const values = points.map(item => Number(item.tokens_saved || 0))
  const max = Math.max(...values, 1)
  return Array.from({ length: 34 }, (_, index) => {
    const value = values[index] || 0
    return value ? Math.max(4, Math.round((value / max) * 28)) : 1
  })
}

function Metric({ icon: Icon, label, value, sub, tone = 'green' }) {
  return (
    <section className={`optimizer-metric kpi-card glass-card optimizer-metric-${tone}`} data-accent={tone}>
      <div className="optimizer-metric-icon"><Icon size={20} /></div>
      <div>
        <div className="optimizer-metric-label">{label}</div>
        <div className="optimizer-metric-value">{value}</div>
        {sub && <div className="optimizer-metric-sub">{sub}</div>}
      </div>
    </section>
  )
}

function BarList({ title, rows, valueKey = 'tokens_saved' }) {
  const max = Math.max(...(rows || []).map(r => Number(r[valueKey] || 0)), 1)
  const total = (rows || []).reduce((sum, row) => sum + Number(row[valueKey] || 0), 0)
  return (
    <section className="optimizer-panel model-card glass-card">
      <div className="optimizer-panel-title">{title}</div>
      <div className="optimizer-bars">
        {(rows || []).slice(0, 6).map(row => (
          <div className="optimizer-bar-row" key={row.model || row.repository}>
            <div className="optimizer-bar-label"><b>{row.model || row.repository || 'unknown'}</b><span>{total ? `${(Number(row[valueKey] || 0) / total * 100).toFixed(1)}%` : '0.0%'}</span></div>
            <div className="optimizer-bar-track">
              <div className="optimizer-bar-fill" style={{ width: `${Math.max(2, Number(row[valueKey] || 0) / max * 100)}%` }} />
            </div>
            <div className="optimizer-bar-value"><b>{formatNumber(row[valueKey])}</b><span>tokens</span></div>
          </div>
        ))}
        {(!rows || rows.length === 0) && <div className="optimizer-empty-small">No data</div>}
      </div>
      <div className="model-total"><span>Total tokens</span><b>{formatNumber(total)}</b></div>
    </section>
  )
}

function ReferenceLogo({ onClick, secretOpen }) {
  return (
    <button className={`reference-logo-button ${secretOpen ? 'is-secret-open' : ''}`} type="button" onClick={onClick} aria-label="Open TrimPy secret">
      <span className="animated-logo" aria-hidden="true">
      <svg viewBox="0 0 140 140" role="img">
        <defs>
          <linearGradient id="ringGradient" x1="0" x2="1"><stop offset="0%" stopColor="#0f766e" /><stop offset="100%" stopColor="#22c55e" /></linearGradient>
          <linearGradient id="arrowGradient" x1="0" x2="1"><stop offset="0%" stopColor="#0f766e" /><stop offset="100%" stopColor="#059669" /></linearGradient>
        </defs>
        <circle className="logo-ring" cx="70" cy="70" r="48" />
        <path className="logo-arrow" d="M70 26 92 84 70 70 48 84Z" />
        <path className="logo-fin" d="M47 79 28 96 44 91Z" />
        <path className="logo-fin" d="M93 79 112 96 96 91Z" />
        <path className="logo-guide" d="M70 72V108" />
        <path className="logo-trim" d="M57 103 70 116 83 103" />
      </svg>
      </span>
    </button>
  )
}

function ConversationRow({ row, expanded, onToggle }) {
  const usage = row.actual_usage?.usage || {}
  const copilotUsage = row.actual_usage?.copilot_usage || {}
  return (
    <>
      <tr className="conversation-row" onClick={onToggle}>
        <td>
          <div className="conversation-time">{formatDateTime(row.compressed_at)}</div>
          <div className="conversation-id">{String(row.session_id || '').slice(0, 18)}</div>
        </td>
        <td>
          <div className="conversation-title">{row.label || row.prompt_preview || 'Copilot request'}</div>
          <div className="conversation-sub">{row.repository || 'unknown repo'} · {row.branch || 'unknown branch'} · {ideName(row.request_source)}</div>
        </td>
        <td>{row.model_used || '—'}</td>
        <td className="num">{formatNumber(row.tokens_before)}</td>
        <td className="num">{formatNumber(row.tokens_after)}</td>
        <td className="num good">{formatNumber(row.tokens_saved)}</td>
        <td className="num">{pct(row.savings_pct)}</td>
        <td className="num">{formatDollars(row.dollars_saved)}</td>
      </tr>
      {expanded && (
        <tr className="conversation-detail-row">
          <td colSpan="8">
            <div className="conversation-detail">
              <div className="trace-score">
                <div>
                  <div className="detail-label">Compression Quality</div>
                  <div className={`grade-chip grade-${row.compression_grade || 'F'}`}>{row.compression_grade || 'F'}</div>
                  <div className="muted">Score {Number(row.compression_score || 0).toFixed(1)} / 100</div>
                </div>
                <div>
                  <div className="detail-label">Actual Usage</div>
                  <div className="usage-grid">
                    <span>Input</span><b>{formatNumber(usage.input_tokens ?? usage.prompt_tokens)}</b>
                    <span>Cached input</span><b>{formatNumber(usage.input_tokens_details?.cached_tokens ?? usage.prompt_tokens_details?.cached_tokens)}</b>
                    <span>Output</span><b>{formatNumber(usage.output_tokens ?? usage.completion_tokens)}</b>
                    <span>Total</span><b>{formatNumber(usage.total_tokens)}</b>
                    <span>AIU</span><b>{formatNumber(copilotUsage.total_nano_aiu)}</b>
                  </div>
                </div>
                <div>
                  <div className="detail-label">Source</div>
                  <div>{row.request_source || 'unknown'}</div>
                  <div className="muted">{row.cwd || 'no cwd captured'}</div>
                </div>
              </div>
              <div>
                <div className="detail-label">Sent</div>
                <pre>{row.prompt_preview || 'No prompt captured'}</pre>
              </div>
              <div>
                <div className="detail-label">Optimized</div>
                <pre>{row.optimized_preview || 'No optimized prompt captured'}</pre>
              </div>
              <div>
                <div className="detail-label">Reply</div>
                <pre>{row.assistant_preview || 'No reply captured'}</pre>
              </div>
              <div className="detail-changes">
                <div className="detail-label">Changes</div>
                {(row.changes || []).length > 0 ? row.changes.map((change, idx) => (
                  <span key={`${change.path}-${idx}`} className="change-pill">
                    <span title={compressionExplain(change.method)}>{change.method}: {formatNumber(change.tokens_before)}→{formatNumber(change.tokens_after)}</span>
                  </span>
                )) : <span className="muted">No field-level compression</span>}
              </div>
              <div className="detail-tips">
                <div className="detail-label">Reduction Tips</div>
                {(row.recommendations || []).map((tip, idx) => <span key={idx}>{tip}</span>)}
              </div>
              <div>
                <div className="detail-label">Full Request Body</div>
                <pre>{row.request_body_preview || 'No request body captured'}</pre>
              </div>
              <div>
                <div className="detail-label">Optimized Body</div>
                <pre>{row.optimized_body_preview || 'No optimized body captured'}</pre>
              </div>
              <div>
                <div className="detail-label">Response Body</div>
                <pre>{row.response_body_preview || 'No response body captured'}</pre>
              </div>
              <div className="debug-log-block">
                <div className="detail-label">Agent Debug Log Context</div>
                <pre>{row.debug_log_preview || 'No nearby Copilot debug log context found'}</pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function CopilotOptimizer({ onNavigate }) {
  const [range, setRange] = useState('day')
  const [granularity, setGranularity] = useState('minute')
  const [summary, setSummary] = useState(null)
  const [daily, setDaily] = useState([])
  const [conversations, setConversations] = useState([])
  const [expanded, setExpanded] = useState(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [liveHealth, setLiveHealth] = useState(null)
  const [showHealth, setShowHealth] = useState(false)
  const [chartRepo, setChartRepo] = useState('')
  const [activity, setActivity] = useState([])
  const [repoQuery, setRepoQuery] = useState('')
  const [repoSort, setRepoSort] = useState('tokens_saved')
  const [secretIndex, setSecretIndex] = useState(0)
  const [secretOpen, setSecretOpen] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [summaryRes, dailyRes, conversationsRes] = await Promise.all([
        fetch(`/api/copilot/summary?range=${range}`),
        fetch(`/api/copilot/timeseries?range=${range}&granularity=${granularity}&repository=${encodeURIComponent(chartRepo)}`),
        fetch(`/api/copilot/conversations?range=${range}&limit=100`),
      ])
      if (summaryRes.ok) setSummary(await summaryRes.json())
      if (dailyRes.ok) {
        const series = await dailyRes.json()
        setDaily(series.points || [])
      }
      if (conversationsRes.ok) setConversations(await conversationsRes.json())
      const activityRes = await fetch(`/api/copilot/activity?range=${range}&limit=12`)
      if (activityRes.ok) setActivity(await activityRes.json())
      const healthRes = await fetch('/api/live-health')
      if (healthRes.ok) setLiveHealth(await healthRes.json())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [range, granularity, chartRepo])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return conversations
    return conversations.filter(row => [
      row.label,
      row.prompt_preview,
      row.repository,
      row.branch,
      row.model_used,
      row.session_id,
    ].some(value => String(value || '').toLowerCase().includes(needle)))
  }, [conversations, query])

  const repoRows = useMemo(() => (summary?.repositories || []).filter(repo => String(repo.repository || '').toLowerCase().includes(repoQuery.toLowerCase())).sort((a, b) => Number(b[repoSort] || 0) - Number(a[repoSort] || 0)), [summary, repoQuery, repoSort])
  const activityHeights = useMemo(() => activitySparkHeights(activity), [activity])

  return (
    <main className="optimizer-page optimizer-reference">
      <header className="optimizer-header topbar">
        <div className="brand-lockup">
          <ReferenceLogo onClick={() => { setSecretIndex(index => (index + 1) % TRIMPY_SECRETS.length); setSecretOpen(true) }} secretOpen={secretOpen} />
          <div><h1>Trim-Pilot</h1><p>Cut Tokens, Keep Context for GitHub Copilot Enterprise.</p></div>
        </div>
        <div className="optimizer-actions topbar-actions">
          <div className="range-picker" role="group" aria-label="Date range">
            {RANGE_OPTIONS.map(([id, label]) => (
              <button key={id} className={range === id ? 'active' : ''} onClick={() => setRange(id)}>
                {label}
              </button>
            ))}
          </div>
          <button className="icon-button round-control" onClick={load} title="Refresh" aria-label="Refresh data">
            <RefreshCw size={16} />
          </button>
          <button className={`live-health-button live-pill ${liveHealth?.status === 'up' ? 'is-up' : 'is-warning'}`} onClick={() => setShowHealth(!showHealth)} aria-label="Live service health">
            <span className="live-dot" />
            <span><strong>{liveHealth?.status === 'up' ? 'Live' : 'Attention'}</strong><small>{liveHealth?.status === 'up' ? 'Working in real time' : 'Check services'}</small></span>
          </button>
        </div>
      </header>
      {secretOpen && <button className="trimpy-secret" type="button" onClick={() => setSecretOpen(false)} aria-label="Close TrimPy secret">
        <Sparkles size={15} />
        <span>{TRIMPY_SECRETS[secretIndex]}</span>
        <span className="trimpy-secret-hint">tap the mark again for another note</span>
      </button>}
      {liveHealth && liveHealth.status !== 'up' && <section className="health-alert" role="alert">
        <XCircle size={18} />
        <div><b>Service attention needed</b><span>{(liveHealth.services || []).filter(s => s.status !== 'up').map(s => `${s.name}: ${healthFix(s)}`).join(' ')}</span></div>
        <button onClick={() => setShowHealth(true)}>View issue</button>
      </section>}
      {showHealth && <section className="live-health-panel">
        <div className="live-health-heading"><div><b>Live service health</b><span>Checked {liveHealth?.checked_at ? formatDateTime(liveHealth.checked_at) : '—'}</span></div><button className="icon-button" onClick={() => setShowHealth(false)} title="Close">×</button></div>
        <div className="live-health-services">{(liveHealth?.services || []).map(service => <div key={service.name} className="live-health-service"><span className={`health-dot ${service.status}`} /><div><b>{service.name}</b><small>{service.detail || service.status}</small></div></div>)}</div>
        <div className="live-health-clients">{(liveHealth?.clients || []).map(client => <div key={client.name}><b>{client.name}</b><span>{formatNumber(client.requests)} requests · {formatNumber(client.tokens_saved)} saved</span></div>)}</div>
      </section>}

      <section className="optimizer-grid kpi-grid stagger">
        <Metric icon={Activity} label="Requests" value={formatNumber(summary?.requests)} sub={`${formatNumber(summary?.conversations)} conversations`} tone="blue" />
        <Metric icon={Zap} label="Tokens Saved" value={formatNumber(summary?.tokens_saved)} sub={`${pct(summary?.savings_pct)} total reduction`} tone="green" />
        <Metric icon={Layers} label="After Optimization" value={formatNumber(summary?.tokens_after)} sub={`${formatNumber(summary?.tokens_before)} before`} tone="purple" />
        <Metric icon={DollarSign} label="Estimated Saved" value={formatDollars(summary?.dollars_saved)} sub="input-token estimate" tone="orange" />
        <Metric icon={Sparkles} label="Avg Request Cut" value={pct(summary?.avg_request_savings_pct)} sub="mean per request" tone="cyan" />
        <Metric icon={Layers} label="GitHub Input" value={formatNumber(summary?.actual_input_tokens)} sub={`${formatNumber(summary?.actual_cached_input_tokens)} cached`} tone="blue" />
      </section>

      <section className="optimizer-context-strip summary-strip glass-card">
        <div className="summary-item"><Clock size={24} /><div><span>Last Request</span><b>{summary?.last_seen ? formatTime(summary.last_seen) : '—'}</b><small>{summary?.last_seen ? formatDateTime(summary.last_seen) : 'waiting'}</small></div></div>
        <div className="summary-item"><Monitor size={24} /><div><span>Computer Time</span><b>{formatDateTime(new Date().toISOString())}</b><small>local machine time</small></div></div>
        <div className="summary-item"><Server size={24} /><div><span>Actual Output</span><b>{formatNumber(summary?.actual_output_tokens)} tokens</b><small>current request</small></div></div>
        <div className="summary-item"><Boxes size={24} /><div><span>Actual Total</span><b>{formatNumber(summary?.actual_total_tokens)} tokens</b><small>upstream usage</small></div></div>
        <div className="summary-item"><ArrowUpRight size={24} /><div><span>How Savings Work</span><b>Before → after</b><small>live estimate</small></div></div>
      </section>
      <section className="system-card glass-card">
        <div className="system-copy"><div className="system-icon"><GitFork size={21} /></div><div><strong>System Design</strong><p>Client → interception → context shaper → GitHub Enterprise → trace</p></div></div>
        <button className="secondary-button" onClick={() => onNavigate?.('system')}>Open system design <ArrowUpRight size={16} /></button>
      </section>
      <section className="optimizer-layout analytics-grid">
        <section className="optimizer-panel optimizer-chart chart-card glass-card">
          <div className="optimizer-chart-heading card-heading"><div><div className="optimizer-panel-title">Request Volume: Actual vs Optimized</div><div className="legend"><span><i className="dot actual" />Actual Request Volume</span><span><i className="dot optimized" />Optimized Sent Volume</span></div></div><div className="chart-filters"><select value={granularity} onChange={e => setGranularity(e.target.value)} aria-label="Chart granularity">{GRANULARITY_OPTIONS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select><select value={chartRepo} onChange={e => setChartRepo(e.target.value)} aria-label="Chart repository"><option value="">All repositories</option>{(summary?.repositories || []).map(repo => <option key={repo.repository} value={repo.repository}>{repo.repository}</option>)}</select></div></div>
          <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={daily}>
              <defs>
                <linearGradient id="savedGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#01A982" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#01A982" stopOpacity={0.08} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(17,24,39,0.09)" />
              <XAxis dataKey="label" tick={{ fill: '#6b7280', fontSize: 11 }} minTickGap={24} />
              <YAxis tick={{ fill: '#9BA3AF', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: '#1A1F28', border: '1px solid #3A4250', color: '#E8EAED' }} />
              <Area type="monotone" dataKey="tokens_before" name="Actual request volume" stroke="#079669" strokeWidth={3} fill="url(#savedGradient)" />
              <Area type="monotone" dataKey="tokens_after" name="Optimized sent volume" stroke="#14b8a6" strokeWidth={2.5} strokeDasharray="7 6" fill="none" />
            </AreaChart>
          </ResponsiveContainer>
          </div>
        </section>
        <BarList title="Model Mix" rows={summary?.model_mix || []} />
      </section>

      <details className="optimizer-panel live-trim-panel activity-strip"><summary><span><i className="pulse-icon"><Activity size={18} /></i><span><b>Live Trim Activity</b><small>{activity.length ? 'Real-time request optimization events' : 'Waiting for a request'}</small></span></span><span className={`activity-spark ${activity.length ? '' : 'is-idle'}`} aria-label={activity.length ? `${activity.length} live trim events` : 'No live trim events'}>{activityHeights.map((height, index) => <i key={index} style={{ height: `${height}px` }} />)}</span><strong>{activity.length} recent events <ChevronRight size={14} /></strong></summary>{activity.length ? <div className="activity-list">{activity.map(item => <div className="activity-row" key={item.id}><span>{item.repository}</span><span>{item.algorithm}</span><b>{formatNumber(item.tokens_saved)} saved</b></div>)}</div> : <div className="optimizer-empty-small">No trim events yet. The activity graph will rise when TrimP receives a request.</div>}</details>

      <details className="optimizer-panel repo-live-panel repository-panel">
        <summary>
          <span className="repository-summary-left"><i className="repo-summary-icon"><GitBranch size={18} /></i><span><b>Repositories</b><small>Tokens, requests, before volume, and reduction</small></span></span>
          <span className="repository-summary-right"><strong>{repoRows.length} shown</strong><ChevronRight size={16} /></span>
        </summary>
        <div className="repository-body">
          <div className="section-heading"><div><h2>Repository savings</h2><p>Search and sort live TrimPy traffic by repository.</p></div><label className="search-box"><Search size={15} /><input value={repoQuery} onChange={e => setRepoQuery(e.target.value)} placeholder="Search repositories" /></label></div>
          <table className="repo-live-table"><thead><tr><th>Repository</th><th>Requests</th><th onClick={() => setRepoSort('tokens_saved')}>Tokens Saved ↓</th><th onClick={() => setRepoSort('tokens_before')}>Before</th><th>Reduction</th><th /></tr></thead><tbody>{repoRows.map(repo => <tr key={repo.repository}><td><div className="repo-name"><GitBranch size={20} /><div><b>{repo.repository}</b><small>Git repository root</small></div></div></td><td>{formatNumber(repo.requests)}</td><td className="good"><b>{formatNumber(repo.tokens_saved)}</b></td><td>{formatNumber(repo.tokens_before)}</td><td className="good"><b>{pct(repo.tokens_saved && repo.tokens_before ? repo.tokens_saved / repo.tokens_before * 100 : 0)}</b></td><td><button className="row-menu" title="Repository actions"><MoreHorizontal size={17} /></button></td></tr>)}</tbody></table>{!repoRows.length && <div className="optimizer-empty-small">No repositories found.</div>}<button className="view-all" onClick={() => setRepoQuery('')}>View all repositories <ChevronDown size={14} /></button>
        </div>
      </details>

      <details className="optimizer-panel conversations-panel conversation-card">
        <summary><span className="conversation-left"><span className="conversation-icon"><MessageSquare size={18} /></span><span><b>Conversations</b><small>Explore conversations and traces</small></span></span><strong>{filtered.length} shown · newest first <ChevronRight size={14} /></strong></summary>
        <div className="conversation-toolbar">
          <div>
            <div className="muted">Search the full trace timeline</div>
          </div>
          <label className="search-box">
            <Search size={15} />
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search prompt, repo, model" />
          </label>
        </div>
        <div className="conversation-table-wrap">
          <table className="conversation-table">
            <thead>
              <tr>
                <th>Date / Time</th>
                <th>Conversation</th>
                <th>Model</th>
                <th className="num">Before</th>
                <th className="num">After</th>
                <th className="num">Saved</th>
                <th className="num">Cut</th>
                <th className="num">$</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(row => (
                <ConversationRow
                  key={row.id}
                  row={row}
                  expanded={expanded === row.id}
                  onToggle={() => setExpanded(expanded === row.id ? null : row.id)}
                />
              ))}
            </tbody>
          </table>
          {!loading && filtered.length === 0 && (
            <div className="optimizer-empty">No Copilot proxy conversations in this range.</div>
          )}
        </div>
      </details>
    </main>
  )
}
