import { useEffect, useMemo, useState } from 'react'
import { Activity, CalendarDays, ChevronLeft, ChevronRight, Download, Filter, MessageSquare, MoreVertical, Search, SlidersHorizontal, Sparkles, Tag, X, Monitor, DollarSign, Database, Code2 } from 'lucide-react'
import { Loading } from '../components/Charts.jsx'

const PERIODS = [
  ['day', 'Last 24 hours'],
  ['week', 'Last 7 days'],
  ['10d', 'Last 10 days'],
  ['15d', 'Last 15 days'],
  ['20d', 'Last 20 days'],
]

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

function formatMoney(value) {
  return `$${Number(value || 0).toFixed(4)}`
}

function parseDate(value) {
  if (!value) return null
  const text = String(value)
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(text) ? text : `${text}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatDate(value) {
  const date = parseDate(value)
  return date ? date.toLocaleDateString([], { month: 'short', day: '2-digit', year: 'numeric' }) : '—'
}

function formatTime(value) {
  const date = parseDate(value)
  return date ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' }) : '—'
}

function modelName(value) {
  return String(value || 'Unknown model').replace(/^github\//, '')
}

function pretty(value) {
  try { return JSON.stringify(value ?? {}, null, 2) } catch { return String(value || '') }
}

function ConversationDetail({ row }) {
  return (
    <tr className="conversation-detail-row">
      <td colSpan="9">
        <div className="conversation-inline-detail">
          <div><span>Prompt sent</span><pre>{row.prompt_preview || 'No prompt captured'}</pre></div>
          <div><span>Optimized context</span><pre>{row.optimized_preview || 'No optimized preview captured'}</pre></div>
          <div><span>Trace</span><pre>{row.debug_log_preview || 'No debug excerpt captured'}</pre></div>
        </div>
      </td>
    </tr>
  )
}

export default function Sessions({ onNavigate }) {
  const [period, setPeriod] = useState('day')
  const [pageSize, setPageSize] = useState(10)
  const [rows, setRows] = useState([])
  const [query, setQuery] = useState('')
  const [model, setModel] = useState('all')
  const [source, setSource] = useState('all')
  const [grade, setGrade] = useState('all')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState(null)
  const [loading, setLoading] = useState(true)
  const [agentRows, setAgentRows] = useState([])
  const [debugSessions, setDebugSessions] = useState([])

  async function load() {
    setLoading(true)
    try {
      const [response, agentResponse, debugResponse] = await Promise.all([
        fetch(`/api/copilot/conversations?range=${period}&limit=500`),
        fetch(`/api/agent-logs/sessions?range=${period}&limit=100`),
        fetch(`/api/copilot/debug-sessions?range=${period}&limit=50`),
      ])
      if (response.ok) setRows(await response.json())
      if (agentResponse.ok) setAgentRows(await agentResponse.json())
      if (debugResponse.ok) setDebugSessions(await debugResponse.json())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setPage(1)
    setExpanded(null)
    load()
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [period])

  const models = useMemo(() => [...new Set(rows.map(row => modelName(row.model_used)))].sort(), [rows])
  const sources = useMemo(() => [...new Set(rows.map(row => row.request_source || 'unknown'))].sort(), [rows])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return rows.filter(row => {
      const matchesText = !needle || [row.label, row.prompt_preview, row.repository, row.branch, row.model_used, row.session_id].some(value => String(value || '').toLowerCase().includes(needle))
      const matchesModel = model === 'all' || modelName(row.model_used) === model
      const matchesSource = source === 'all' || (row.request_source || 'unknown') === source
      const matchesGrade = grade === 'all' || (row.compression_grade || 'F') === grade
      return matchesText && matchesModel && matchesSource && matchesGrade
    })
  }, [rows, query, model, source, grade])

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const visibleRows = filtered.slice((page - 1) * pageSize, page * pageSize)
  const totals = useMemo(() => {
    const before = filtered.reduce((sum, row) => sum + Number(row.tokens_before || 0), 0)
    const saved = filtered.reduce((sum, row) => sum + Number(row.tokens_saved || 0), 0)
    const reductions = filtered.map(row => Number(row.savings_pct || 0))
    return { before, saved, reduction: reductions.length ? reductions.reduce((sum, value) => sum + value, 0) / reductions.length : 0, dollars: filtered.reduce((sum, row) => sum + Number(row.dollars_saved || 0), 0) }
  }, [filtered])

  function exportRows() {
    const header = ['date', 'repository', 'model', 'before', 'after', 'saved', 'reduction', 'cost']
    const lines = filtered.map(row => [row.compressed_at, row.repository || '', modelName(row.model_used), row.tokens_before || 0, row.tokens_after || 0, row.tokens_saved || 0, row.savings_pct || 0, row.dollars_saved || 0].map(value => JSON.stringify(value)).join(','))
    const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `trimp-conversations-${period}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  if (loading && !rows.length) return <Loading />

  return (
    <main className="conversation-reference">
      <header className="conversation-page-header">
        <div>
          <div className="conversation-kicker"><MessageSquare size={15} /> TrimPy trace browser</div>
          <h1>Conversations</h1>
          <p>Explore traces, prompts, and token optimization history.</p>
        </div>
        <button className="feedback-button" onClick={() => onNavigate?.('feedback')}><MessageSquare size={15} /> Give feedback</button>
      </header>

      <section className="conversation-controls">
        <label className="conversation-search"><Search size={17} /><input value={query} onChange={event => { setQuery(event.target.value); setPage(1) }} placeholder="Search by prompt, repo, model, or trace ID…" /><kbd>⌘ K</kbd></label>
        <button className={`conversation-control-button ${filtersOpen ? 'selected' : ''}`} onClick={() => setFiltersOpen(value => !value)}><Filter size={16} /> Filters <span>{[model !== 'all', source !== 'all', grade !== 'all'].filter(Boolean).length || ''}</span></button>
        <label className="conversation-select"><CalendarDays size={16} /><select value={period} onChange={event => setPeriod(event.target.value)} aria-label="Conversation period">{PERIODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><ChevronDownIcon /></label>
        <label className="conversation-select compact-select"><Tag size={16} /><select value={model} onChange={event => { setModel(event.target.value); setPage(1) }} aria-label="Filter by model"><option value="all">All models</option>{models.map(value => <option key={value} value={value}>{value}</option>)}</select><ChevronDownIcon /></label>
        <label className="conversation-select compact-select"><SlidersHorizontal size={16} /><select value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(1) }} aria-label="Rows per page"><option value="10">10 rows</option><option value="15">15 rows</option><option value="20">20 rows</option></select><ChevronDownIcon /></label>
        <button className="export-button" onClick={exportRows}><Download size={16} /> Export</button>
      </section>

      {filtersOpen && <section className="conversation-filter-panel"><label>Client / source<select value={source} onChange={event => { setSource(event.target.value); setPage(1) }}><option value="all">All sources</option>{sources.map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>Compression grade<select value={grade} onChange={event => { setGrade(event.target.value); setPage(1) }}><option value="all">All grades</option>{['A', 'B', 'C', 'D', 'F'].map(value => <option key={value} value={value}>{value}</option>)}</select></label><button className="clear-filter-button" onClick={() => { setModel('all'); setSource('all'); setGrade('all'); setQuery(''); setPage(1) }}><X size={14} /> Clear filters</button></section>}

      <section className="conversation-summary-grid">
        <SummaryCard icon={MessageSquare} label="Conversations" value={formatNumber(filtered.length)} sub="in selected period" />
        <SummaryCard icon={Sparkles} label="Avg. Token Savings" value={formatNumber(filtered.length ? totals.saved / filtered.length : 0)} sub="per conversation" />
        <SummaryCard icon={SlidersHorizontal} label="Token Reduction" value={`${totals.reduction.toFixed(2)}%`} sub="average reduction" />
        <SummaryCard icon={Tag} label="Estimated Cost Saved" value={formatMoney(totals.dollars)} sub="total saved" />
      </section>

      <section className="debug-session-card">
        <header className="debug-session-card-header">
          <div><div className="conversation-kicker"><Monitor size={14} /> IDE session trace</div><h2>Conversations grouped by session</h2><p>One IDE session contains every chat and model request. Expand a session to inspect exact upstream usage, context, and cost.</p></div>
          <span className="usage-source-badge reported">{debugSessions.length} IDE sessions</span>
        </header>
        <div className="debug-session-list">
          {debugSessions.map(session => <DebugSessionGroup key={session.session_id} session={session} />)}
          {!debugSessions.length && <div className="conversation-empty">No IDE debug sessions found for this period.</div>}
        </div>
      </section>

      <section className="agent-log-table-card"><header><div><div className="conversation-kicker"><Activity size={14} /> Exact upstream usage</div><h2>GitHub Copilot Agent Debug Logs</h2><p>Session snapshots imported from local <code>events.jsonl</code> files. Cached input, output, turns, tools, and totals are reported by Copilot.</p></div><span className="usage-source-badge reported">{agentRows.length} sessions</span></header><div className="agent-log-table-wrap"><table className="agent-log-table"><thead><tr><th>Time</th><th>Repository</th><th>Model</th><th>Input</th><th>Cached</th><th>Output</th><th>Total</th><th>Turns</th><th>Tools</th><th>Errors</th></tr></thead><tbody>{agentRows.map(row => <tr key={row.source_session_id}><td><b>{formatDate(row.event_end)}</b><small>{formatTime(row.event_end)}</small></td><td><b>{row.repository || row.cwd || 'Unknown repository'}</b><small>{row.source_session_id}</small></td><td><span className="model-pill">{modelName(row.model)}</span></td><td>{formatNumber(row.input_tokens)}</td><td>{formatNumber(row.cached_input_tokens)}</td><td>{formatNumber(row.output_tokens)}</td><td className="saved-value">{formatNumber(row.total_tokens)}</td><td>{formatNumber(row.model_turns)}</td><td>{formatNumber(row.tool_calls)}</td><td>{formatNumber(row.errors)}</td></tr>)}</tbody></table>{!agentRows.length && <div className="conversation-empty">No local agent usage snapshots found for this period.</div>}</div></section>

      <section className="conversation-table-card">
        <table className="conversation-browser-table">
          <thead><tr><th></th><th>Date / Time ↓</th><th>Conversation</th><th>Model</th><th>Before</th><th>After</th><th>Saved</th><th>Reduction</th><th>Cost</th><th></th></tr></thead>
          <tbody>{visibleRows.map(row => <ConversationBrowserRow key={row.id} row={row} expanded={expanded === row.id} onToggle={() => setExpanded(expanded === row.id ? null : row.id)} />)}</tbody>
        </table>
        {!visibleRows.length && <div className="conversation-empty">No conversations match the selected filters.</div>}
        <footer className="conversation-pagination"><span>Showing {filtered.length ? (page - 1) * pageSize + 1 : 0} to {Math.min(page * pageSize, filtered.length)} of {formatNumber(filtered.length)} conversations</span><div><span>Rows per page</span><label className="pagination-select"><select value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(1) }}><option value="10">10</option><option value="15">15</option><option value="20">20</option></select><ChevronDownIcon /></label><button disabled={page <= 1} onClick={() => setPage(value => Math.max(1, value - 1))} aria-label="Previous page"><ChevronLeft size={16} /></button><b>{page}</b><button disabled={page >= totalPages} onClick={() => setPage(value => Math.min(totalPages, value + 1))} aria-label="Next page"><ChevronRight size={16} /></button></div></footer>
      </section>
    </main>
  )
}

function ChevronDownIcon() {
  return <span className="select-chevron"><ChevronRight size={14} /></span>
}

function SummaryCard({ icon: Icon, label, value, sub }) {
  return <article className="conversation-summary-card"><span className="conversation-summary-icon"><Icon size={21} /></span><div><span>{label}</span><strong>{value}</strong><small>{sub}</small></div></article>
}

function DebugSessionGroup({ session }) {
  const [open, setOpen] = useState(false)
  const exact = session.primary_usage || {}
  const trim = session.trimpy || {}
  const exactUsage = session.usage_source === 'ide_debug_log'
  const usageLabel = exactUsage ? 'exact input' : 'observed input'
  return (
    <article className={`debug-session-group ${open ? 'is-open' : ''}`}>
      <button className="debug-session-summary" onClick={() => setOpen(value => !value)} aria-expanded={open}>
        <span className="debug-session-chevron"><ChevronRight size={17} /></span>
        <span className="debug-session-main"><strong>{session.repository || 'Unknown repository'}</strong><small>{session.ide} · {formatDate(session.started_at)} {formatTime(session.started_at)} · {session.request_count} model requests</small><code>{session.session_id}</code></span>
        <span className="debug-session-stat"><b>{formatNumber(exact.input_tokens)}</b><small>{usageLabel}</small></span>
        <span className="debug-session-stat"><b>{formatNumber(exact.cached_tokens)}</b><small>cached</small></span>
        <span className="debug-session-stat"><b>{formatMoney(session.exact_cost_estimate)}</b><small>cost estimate</small></span>
      </button>
      {open && <div className="debug-session-detail">
        <div className="debug-session-meta"><span><Monitor size={14} /> {session.ide}</span><span><Code2 size={14} /> {session.cwd || 'Workspace unavailable'}</span><span><Database size={14} /> {session.model_turns} primary chats, {session.request_count - session.model_turns} supporting requests</span></div>
        <div className="debug-metric-grid">
          <Metric label={exactUsage ? 'Exact input' : 'Observed input'} value={formatNumber(exact.input_tokens)} note={exactUsage ? 'reported by IDE' : 'proxy response or sent volume'} />
          <Metric label="Cached input" value={formatNumber(exact.cached_tokens)} note="included in input" />
          <Metric label="Exact output" value={formatNumber(exact.output_tokens)} note="reported by IDE" />
          <Metric label="Exact total" value={formatNumber(exact.total_tokens)} note="input + output" />
          <Metric label="Cost estimate" value={formatMoney(session.exact_cost_estimate)} note="all model requests" />
          <Metric label="TrimPy cost avoided" value={formatMoney(trim.estimated_cost_saved)} note={`${formatNumber(trim.tokens_saved)} estimated tokens`} />
        </div>
        <div className="debug-session-note"><DollarSign size={14} /><span><b>How cost is calculated:</b> uncached input × input rate + cached input × cache-read rate + output × output rate. {session.pricing_basis}.</span></div>
        {trim.requests > 0 && <div className="debug-trim-comparison"><b>TrimPy correlation near this session</b><span>{formatNumber(trim.tokens_before)} before → {formatNumber(trim.tokens_after)} after · {formatNumber(trim.tokens_saved)} estimated saved · {trim.savings_pct}% reduction</span></div>}
        <div className="debug-turn-list">
          {session.turns.map((turn, index) => <DebugTurn key={turn.source_key || index} turn={turn} index={index} />)}
        </div>
      </div>}
    </article>
  )
}

function Metric({ label, value, note }) {
  return <div className="debug-metric"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
}

function DebugTurn({ turn, index }) {
  const [open, setOpen] = useState(false)
  return <article className={`debug-turn ${turn.request_kind === 'supporting' ? 'supporting' : ''}`}>
    <button className="debug-turn-summary" onClick={() => setOpen(value => !value)} aria-expanded={open}>
      <span className="debug-turn-number">{turn.request_kind === 'primary' ? `Chat ${turn.turn_index + 1}` : 'Supporting'}</span>
      <span className="debug-turn-prompt"><b>{turn.user_message || turn.debug_name || 'Model request'}</b><small>{modelName(turn.model)} · {formatTime(turn.occurred_at)} · {turn.status}</small></span>
      <span><b>{formatNumber(turn.input_tokens)}</b><small>input</small></span><span><b>{formatNumber(turn.cached_tokens)}</b><small>cached</small></span><span><b>{formatNumber(turn.output_tokens)}</b><small>output</small></span><span className="saved-value"><b>{formatMoney(turn.exact_cost_estimate)}</b><small>estimate</small></span><ChevronRight className="debug-turn-arrow" size={16} />
    </button>
    {open && <div className="debug-turn-detail">
      <div className="debug-turn-context-summary"><span><b>Uncached input</b> {formatNumber(turn.uncached_input_tokens)}</span><span><b>TTFT</b> {formatNumber(turn.ttft_ms)} ms</span><span><b>Max output</b> {formatNumber(turn.max_output_tokens)}</span><span><b>Response status</b> {turn.status}</span></div>
      {turn.user_message && <div className="debug-prompt-block"><label>User chat</label><pre>{turn.user_message}</pre></div>}
      <details open><summary>Full context sent to model</summary><pre>{pretty(turn.context)}</pre></details>
      <details><summary>Raw debug trace</summary><pre>{pretty(turn.trace)}</pre></details>
    </div>}
  </article>
}

function ConversationBrowserRow({ row, expanded, onToggle }) {
  return <>
    <tr className={expanded ? 'is-expanded' : ''} onClick={onToggle}>
      <td className="conversation-expand"><ChevronRight size={16} /></td>
      <td><b>{formatDate(row.compressed_at)}</b><small>{formatTime(row.compressed_at)}</small></td>
      <td className="browser-conversation"><div><b>{row.repository || 'Unknown repository'}</b><span>/</span><strong>{row.label || row.session_id || 'Copilot request'}</strong></div><small>{row.prompt_preview || 'No prompt captured'}</small></td>
      <td><span className="model-pill">{modelName(row.model_used)}</span></td>
      <td>{formatNumber(row.tokens_before)}</td>
      <td>{formatNumber(row.tokens_after)}</td>
      <td className="saved-value">{formatNumber(row.tokens_saved)}</td>
      <td className="saved-value">{Number(row.savings_pct || 0).toFixed(2)}%</td>
      <td>{formatMoney(row.dollars_saved)}</td>
      <td><button className="conversation-row-menu" onClick={event => event.stopPropagation()} title="Conversation actions"><MoreVertical size={16} /></button></td>
    </tr>
    {expanded && <ConversationDetail row={row} />}
  </>
}
