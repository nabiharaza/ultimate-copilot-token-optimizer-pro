import { useEffect, useMemo, useState } from 'react'
import { Activity, CalendarDays, CheckCircle2, ChevronDown, ChevronRight, CircleX, FolderGit2, History, Pencil, Search, ShieldCheck, Sparkles } from 'lucide-react'
import { useRefreshTick } from '../hooks/useApi.js'

function lines(value) { return String(value || '').split('\n') }
function labelFor(method) { return String(method || 'context trim').replaceAll('-', ' ') }
function dateValue(value) { if (!value) return null; const text = String(value); const parsed = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(text) ? text : `${text}Z`); return Number.isNaN(parsed.getTime()) ? null : parsed }
function formatDate(value, options = {}) { const date = dateValue(value); return date ? date.toLocaleString([], options) : 'Unknown time' }
function isActive(value) { const date = dateValue(value); return Boolean(date && Date.now() - date.getTime() >= -5000 && Date.now() - date.getTime() <= 10 * 60 * 1000) }
function number(value) { return Number(value || 0).toLocaleString() }

export default function DiffReview() {
  const [rows, setRows] = useState([])
  const [selected, setSelected] = useState(null)
  const [repository, setRepository] = useState('')
  const [repositoryOptions, setRepositoryOptions] = useState([])
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedDetail, setSelectedDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)
  const [reviewSearch, setReviewSearch] = useState('')
  const [detailType, setDetailType] = useState('removed')
  const [focusedChange, setFocusedChange] = useState(null)
  const refreshTick = useRefreshTick()
  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams({ range: 'all', limit: '250' })
    if (repository) params.set('repository', repository)
    if (startDate) params.set('start_date', startDate)
    if (endDate) params.set('end_date', endDate)
    // Same reasoning as Repositories/Sessions/Alerts: this effect also re-runs
    // on every 1s refreshTick, so only show the loading state on first load or
    // a real filter change, not on every background poll.
    if (refreshTick === 0) setLoading(true)
    fetch(`/api/copilot/conversations?${params}`, { signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error(`Unable to load reviews (${response.status})`); return response.json() })
      .then(data => {
        setRows(data)
        if (!repository && !startDate && !endDate) setRepositoryOptions([...new Set(data.map(row => row.repository).filter(Boolean))].sort())
        setSelected(current => data.find(row => String(row.id) === String(current?.id)) || data[0] || null)
        setError('')
      })
      .catch(fetchError => { if (fetchError.name !== 'AbortError') setError(fetchError.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [repository, startDate, endDate, refreshTick])
  useEffect(() => {
    if (!selected?.id) { setSelectedDetail(null); return }
    const controller = new AbortController()
    setDetailLoading(true)
    fetch(`/api/copilot/conversations/${selected.id}/diff`, { signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error(`Unable to load review details (${response.status})`); return response.json() })
      .then(setSelectedDetail)
      .catch(fetchError => { if (fetchError.name !== 'AbortError') setError(fetchError.message) })
      .finally(() => { if (!controller.signal.aborted) setDetailLoading(false) })
    return () => controller.abort()
  }, [selected?.id])
  const original = useMemo(() => lines(selectedDetail?.original_text), [selectedDetail])
  const optimized = useMemo(() => lines(selectedDetail?.compressed_text), [selectedDetail])
  const changes = selectedDetail?.changes || []
  const lineChanges = selectedDetail?.line_changes || { counts: { removed: 0, kept: 0, modified: 0 }, entries: [] }
  const beforeLineTypes = useMemo(() => new Map(lineChanges.entries.filter(entry => entry.before_line).map(entry => [entry.before_line, entry.type])), [lineChanges])
  const afterLineTypes = useMemo(() => new Map(lineChanges.entries.filter(entry => entry.after_line).map(entry => [entry.after_line, entry.type])), [lineChanges])
  const current = rows.find(row => isActive(row.compressed_at)) || null
  const saved = Number(selected?.tokens_before || 0) - Number(selected?.tokens_after || 0)
  function scrollPaneToLine(selector, line) {
    if (!line) return
    const pane = document.querySelector(selector)
    const target = pane?.querySelector(`[data-line="${line}"]`)
    if (pane && target) pane.scrollTo({ top: Math.max(0, target.offsetTop - pane.clientHeight / 2), behavior: 'smooth' })
  }
  function showChangeType(type) {
    setDetailType(type)
    const entryIndex = lineChanges.entries.findIndex(item => item.type === type)
    const entry = entryIndex >= 0 ? lineChanges.entries[entryIndex] : null
    const nearbyBefore = entry?.before_line || lineChanges.entries.slice(entryIndex + 1).find(item => item.before_line)?.before_line || lineChanges.entries.slice(0, entryIndex).reverse().find(item => item.before_line)?.before_line
    const nearbyAfter = entry?.after_line || lineChanges.entries.slice(entryIndex + 1).find(item => item.after_line)?.after_line || lineChanges.entries.slice(0, entryIndex).reverse().find(item => item.after_line)?.after_line
    setFocusedChange(entry ? `${entry.before_line || 'x'}:${entry.after_line || 'x'}:${type}` : null)
    window.requestAnimationFrame(() => {
      scrollPaneToLine('.diff-before-pane', nearbyBefore)
      scrollPaneToLine('.diff-after-pane', nearbyAfter)
      document.querySelector('.diff-columns')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }
  function syncDiffScroll(event) {
    // Deliberately independent: paired navigation only happens when a
    // Removed, Kept, or Modified metric is clicked.
  }
  function clearFilters() {
    setRepository('')
    setStartDate('')
    setEndDate('')
    setSelected(null)
  }
  return <main className="diff-page">
    <header className="diff-hero"><div><div className="optimizer-kicker"><ShieldCheck size={15} /> Trust and safety</div><h1>Diff review</h1><p>Inspect what TrimPy changed by repository and date in a paired request comparison.</p></div>{selected && <div className="diff-total-card"><span>Tokens reduced</span><strong>{Number(selected.savings_pct || 0).toFixed(2)}%</strong><b>{number(selected.tokens_before)} <span>→</span> {number(selected.tokens_after)}</b><small>{number(saved)} tokens saved</small></div>}</header>
    <section className="diff-filter-bar">
      <label><FolderGit2 size={15} /><span>Repository</span><select value={repository} onChange={event => { setRepository(event.target.value); setSelected(null) }}><option value="">All repositories</option>{repositoryOptions.map(name => <option key={name} value={name}>{name}</option>)}</select></label>
      <label><CalendarDays size={15} /><span>From</span><input type="date" value={startDate} onChange={event => { const value = event.target.value; setStartDate(value); setEndDate(current => current || value); setSelected(null) }} /></label>
      <label><CalendarDays size={15} /><span>To <i>(optional)</i></span><input type="date" min={startDate || undefined} value={endDate} onChange={event => { setEndDate(event.target.value); setSelected(null) }} /></label>
      <ReviewPicker rows={rows} selected={selected} open={reviewOpen} setOpen={setReviewOpen} search={reviewSearch} setSearch={setReviewSearch} loading={loading} onSelect={row => { setSelected(row); setReviewOpen(false) }} />
      {(repository || startDate || endDate) && <button className="diff-clear-filter" onClick={clearFilters}>Clear</button>}
    </section>
    {error && <div className="trimp-config-error" role="alert">{error}</div>}
    <section className={`diff-current-work ${current ? 'is-live' : ''}`}><span className="diff-current-icon"><Activity size={17} /></span><div><small>Currently being worked on</small><strong>{current ? current.label || current.prompt_preview || `${current.repository} request` : 'No active request in the last 10 minutes'}</strong><p>{current ? `${current.repository || 'Unknown repository'} · ${current.branch || 'unknown branch'} · ${current.model_used || 'unknown model'}` : 'The latest matching review will appear here when traffic is detected.'}</p></div>{current && <><span className="diff-live-pill">Live</span><button onClick={() => setSelected(current)}>Open current <ChevronRight size={14} /></button></>}</section>
    {selected ? <>
      <section className="diff-toolbar"><div><b>{selected.repository || 'Unknown repository'}</b><span>{selected.branch || 'unknown branch'} · {selected.model_used || 'unknown model'} · #{selected.id}</span></div><span className={isActive(selected.compressed_at) ? 'diff-live-pill' : 'diff-review-time'}>{isActive(selected.compressed_at) ? 'Active now' : formatDate(selected.compressed_at, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span></section>
      <section className="diff-card"><div className="diff-card-header"><div><h2>Trim preview — {selected.repository || 'request'}</h2><p>Policy: balanced · {number(selected.tokens_before)} → {number(selected.tokens_after)} tokens <mark>{Number(selected.savings_pct || 0).toFixed(2)}% successful reduction</mark></p></div><div className="diff-change-metrics"><ChangeMetric type="removed" icon={CircleX} count={lineChanges.counts.removed} active={detailType === 'removed'} onClick={showChangeType} /><ChangeMetric type="kept" icon={CheckCircle2} count={lineChanges.counts.kept} active={detailType === 'kept'} onClick={showChangeType} /><ChangeMetric type="modified" icon={Pencil} count={lineChanges.counts.modified} active={detailType === 'modified'} onClick={showChangeType} /><span className="net"><b>{number(saved)}</b> tokens reduced</span></div></div>{detailLoading ? <div className="diff-detail-loading">Comparing the complete request payload…</div> : <><div className="diff-columns"><div><div className="diff-column-title">Before (original request) <span>{number(original.length)} lines</span></div><pre className="diff-before-pane" onScroll={syncDiffScroll}>{original.map((line, index) => { const lineNumber = index + 1; const type = beforeLineTypes.get(lineNumber) || 'kept'; const entry = lineChanges.entries.find(item => item.before_line === lineNumber && item.type === type); const key = entry ? `${entry.before_line || 'x'}:${entry.after_line || 'x'}:${type}` : ''; return <span data-line={lineNumber} className={`diff-line change-${type} ${focusedChange === key ? 'focused' : ''}`} key={index}><i>{type === 'removed' ? '−' : type === 'modified' ? '~' : ' '}{lineNumber}</i>{line || ' '}</span> })}</pre></div><div><div className="diff-column-title">After (sent to model) <span>{number(optimized.length)} lines</span></div><pre className="diff-after-pane" onScroll={syncDiffScroll}>{optimized.map((line, index) => { const lineNumber = index + 1; const type = afterLineTypes.get(lineNumber) || 'kept'; const entry = lineChanges.entries.find(item => item.after_line === lineNumber && item.type === type); const key = entry ? `${entry.before_line || 'x'}:${entry.after_line || 'x'}:${type}` : ''; const omitted = /^\s*(\.\.\.|\[\.\.\.\])\s*$/.test(line); return <span data-line={lineNumber} className={`diff-line change-${type} ${focusedChange === key ? 'focused' : ''} ${omitted ? 'omission-marker' : ''}`} key={index}><i>{type === 'modified' ? '~' : ' '}{lineNumber}</i>{line || ' '}{omitted && <em>Earlier content was condensed—open Modified details.</em>}</span> })}</pre></div></div><div className="diff-sync-note">Before and After scroll together · <b>~</b> modified · <b>−</b> removed</div><AttributionSummary changes={changes} /></>}</section>
    </> : <div className="empty-state">{loading ? 'Loading matching reviews…' : 'No reviews match this repository and date.'}</div>}
  </main>
}

function ReviewPicker({ rows, selected, open, setOpen, search, setSearch, loading, onSelect }) {
  const visible = rows.filter(row => `${row.id} ${row.model_used} ${row.repository} ${row.label}`.toLowerCase().includes(search.toLowerCase()))
  return <div className="diff-review-picker"><span><History size={15} /> Review</span><button type="button" onClick={() => setOpen(value => !value)} disabled={loading && !rows.length}><div><b>{selected ? formatDate(selected.compressed_at, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : loading ? 'Loading reviews…' : 'No matching reviews'}</b>{selected && <small>{selected.model_used || 'Unknown model'} · balanced · #{selected.id}</small>}</div>{selected && <mark>{Number(selected.savings_pct || 0).toFixed(2)}%</mark>}<ChevronDown size={14} /></button>{open && <div className="diff-review-menu"><label><Search size={14} /><input autoFocus value={search} onChange={event => setSearch(event.target.value)} placeholder="Search reviews, model or ID…" /></label><div className="diff-review-menu-list">{visible.map(row => <button type="button" key={row.id} className={row.id === selected?.id ? 'selected' : ''} onClick={() => onSelect(row)}><CalendarDays size={13} /><span><b>{formatDate(row.compressed_at, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })} · #{row.id}</b><small>{row.model_used || 'Unknown model'} · balanced · {number(row.tokens_before)} → {number(row.tokens_after)}</small></span><mark>{Number(row.savings_pct || 0).toFixed(2)}%</mark>{row.id === selected?.id && <CheckCircle2 size={14} />}</button>)}{!visible.length && <p>No reviews match this search and date range.</p>}</div></div>}</div>
}

function ChangeMetric({ type, icon: Icon, count, active, onClick }) {
  return <button type="button" className={`${type} ${active ? 'active' : ''}`} onClick={() => onClick(type)} disabled={!count}><Icon size={15} /><span><small>{type}</small><b>{number(count)} lines</b></span></button>
}

function AttributionSummary({ changes }) {
  if (!changes.length) return <div className="diff-attribution"><span>No algorithm attribution was captured for this request.</span></div>
  const saved = changes.reduce((sum, change) => sum + Number(change.tokens_saved || 0), 0)
  return <details className="diff-attribution-details"><summary><span><Sparkles size={13} /> Compression methods</span><b>{changes.length} transformations · {number(saved)} attributed tokens saved</b><ChevronDown size={14} /></summary><div className="diff-attribution">{changes.map((change, index) => <span key={index} className="diff-tag"><Sparkles size={12} /> {labelFor(change.method)} · {number(change.tokens_saved)} saved</span>)}</div></details>
}
