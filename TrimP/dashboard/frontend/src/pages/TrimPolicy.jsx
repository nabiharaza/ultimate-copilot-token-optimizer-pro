import { useEffect, useState } from 'react'
import { Save, SlidersHorizontal } from 'lucide-react'

const ALGORITHMS = [
  ['semantic_dedup', 'Semantic dedup', 'Collapse near-duplicate code blocks in context'],
  ['stale_context', 'Stale context prune', 'Drop unused imports and old file references'],
  ['comment_strip', 'Comment stripping', 'Remove stale TODOs and non-essential comments'],
  ['whitespace', 'Whitespace / format', 'Collapse blank lines and redundant indentation'],
  ['imports', 'Import consolidation', 'Merge repeated import statements across files'],
  ['docstrings', 'Docstring truncation', 'Shorten long docstrings to their first useful line'],
  ['logs', 'Log statement trimming', 'Remove verbose logging calls from included context'],
  ['tests', 'Test fixture pruning', 'Exclude unrelated test fixtures from the request'],
  ['strings', 'Long string truncation', 'Shorten long string and byte literals in context'],
  ['history', 'Historical diff pruning', 'Drop old diff hunks no longer relevant to the request'],
]

export default function TrimPolicy() {
  const [repo, setRepo] = useState('all repositories')
  const [policy, setPolicy] = useState('balanced')
  const [enabled, setEnabled] = useState(Object.fromEntries(ALGORITHMS.map(([id]) => [id, !['docstrings', 'strings'].includes(id)])))
  const [repos, setRepos] = useState([])
  const [saved, setSaved] = useState(false)
  useEffect(() => { fetch('/api/repositories').then(r => r.json()).then(data => setRepos(data.repositories || [])) }, [])
  function choosePolicy(value) {
    setPolicy(value)
    if (value === 'conservative') setEnabled(Object.fromEntries(ALGORITHMS.map(([id]) => [id, ['whitespace', 'imports'].includes(id)])))
    if (value === 'balanced') setEnabled(Object.fromEntries(ALGORITHMS.map(([id]) => [id, !['docstrings', 'strings'].includes(id)])))
    if (value === 'aggressive') setEnabled(Object.fromEntries(ALGORITHMS.map(([id]) => [id, true])))
  }
  const reduction = policy === 'aggressive' ? 44 : policy === 'conservative' ? 16 : 31
  async function save() {
    await fetch('/api/config/compression.policy', { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ value: policy }) })
    setSaved(true); setTimeout(() => setSaved(false), 1600)
  }
  return <main className="policy-page">
    <header className="optimizer-header"><div><div className="optimizer-kicker"><SlidersHorizontal size={15} /> Governance</div><h1>Trim policy</h1><p>Choose how much context TrimP removes for each repository.</p></div></header>
    <section className="policy-panel">
      <label className="policy-label">Repository</label><select value={repo} onChange={e => setRepo(e.target.value)}><option>all repositories</option>{repos.map(item => <option key={item.repository}>{item.repository}</option>)}</select>
      <div className="policy-modes">{['conservative','balanced','aggressive'].map(value => <button key={value} className={policy === value ? 'selected' : ''} onClick={() => choosePolicy(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div>
      <p className="policy-description">{policy === 'conservative' ? 'Preserves nearly all context and only removes obvious formatting noise.' : policy === 'aggressive' ? 'Maximizes reduction and requires diff review for sensitive repositories.' : 'Trims duplicate and stale context while preserving review-critical comments and docstrings.'}</p>
      <div className="policy-list">{ALGORITHMS.map(([id, label, help]) => <label className="policy-row" key={id}><span><b>{label}</b><small>{help}</small></span><input type="checkbox" checked={!!enabled[id]} onChange={e => setEnabled({...enabled, [id]: e.target.checked})} /></label>)}</div>
      <div className="policy-footer"><span>Estimated reduction with this configuration: <b>{reduction}%</b></span><button className="primary-button" onClick={save}><Save size={15} /> {saved ? 'Saved' : 'Save changes'}</button></div>
    </section>
  </main>
}
