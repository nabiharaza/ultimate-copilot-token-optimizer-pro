import { useEffect, useMemo, useState } from 'react'
import { Check, RotateCcw, ShieldCheck } from 'lucide-react'

function lines(value) { return String(value || '').split('\n') }
function labelFor(method) { return String(method || 'context trim').replaceAll('-', ' ') }

export default function DiffReview() {
  const [rows, setRows] = useState([])
  const [selected, setSelected] = useState(null)
  const [restored, setRestored] = useState(new Set())
  useEffect(() => { fetch('/api/copilot/conversations?range=all&limit=50').then(r => r.json()).then(data => { setRows(data); setSelected(data[0] || null) }) }, [])
  const original = useMemo(() => lines(selected?.original_text), [selected])
  const optimized = useMemo(() => lines(selected?.compressed_text), [selected])
  const changes = selected?.changes || []
  function restore(index) { setRestored(new Set([...restored, index])) }
  return <main className="diff-page">
    <header className="optimizer-header"><div><div className="optimizer-kicker"><ShieldCheck size={15} /> Trust and safety</div><h1>Diff review</h1><p>Every removed field stays inspectable, attributed, and restorable before policy approval.</p></div></header>
    <section className="diff-toolbar"><select value={selected?.id || ''} onChange={e => setSelected(rows.find(row => String(row.id) === e.target.value))}>{rows.map(row => <option key={row.id} value={row.id}>{row.repository || 'unknown repo'} · {row.model_used} · {row.id}</option>)}</select><span>{selected ? `${selected.tokens_before?.toLocaleString()} → ${selected.tokens_after?.toLocaleString()} tokens` : 'No traces yet'}</span><button className="secondary-button" onClick={() => setRestored(new Set())}><RotateCcw size={15} /> Restore all</button><button className="primary-button"><Check size={15} /> Approve</button></section>
    {selected ? <section className="diff-card"><div className="diff-card-header"><div><h2>Trim preview — {selected.repository || 'request'}</h2><p>Policy: balanced · {selected.tokens_before?.toLocaleString()} → {selected.tokens_after?.toLocaleString()} tokens ({selected.savings_pct || 0}% reduction)</p></div></div><div className="diff-columns"><div><div className="diff-column-title">Before</div><pre>{original.map((line, index) => <span className="diff-line" key={index}>{line || ' '}</span>)}</pre></div><div><div className="diff-column-title">After</div><pre>{optimized.map((line, index) => <span className="diff-line kept" key={index}>{line || ' '}</span>)}</pre></div></div><div className="diff-attribution">{changes.length ? changes.map((change, index) => <button key={index} className={`diff-tag ${restored.has(index) ? 'restored' : ''}`} title="Restore this field in the next policy run" onClick={() => restore(index)}>{labelFor(change.method)} · {change.tokens_saved?.toLocaleString()} saved {restored.has(index) ? '· restored' : '↩'}</button>) : <span>No field-level changes were captured for this request.</span>}</div></section> : <div className="empty-state">Send a request through TrimP to create an auditable diff.</div>}
  </main>
}
