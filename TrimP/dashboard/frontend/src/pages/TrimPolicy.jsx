import { useEffect, useMemo, useState } from 'react'
import { BarChart3, Check, ChevronDown, Info, Lightbulb, RotateCcw, Save, Scale, ShieldCheck, SlidersHorizontal, Sparkles, Zap } from 'lucide-react'

const ALGORITHMS = [
  ['semantic_dedup', 'Semantic deduplication', 'Collapse near-duplicate code blocks and content.', ShieldCheck, 'Removes repeated context while preserving one canonical block.'],
  ['stale_context', 'Stale context pruning', 'Drop unused imports and old file references.', Sparkles, 'Removes files and symbols no longer connected to the active request.'],
  ['comment_strip', 'Comment stripping', 'Remove stale TODOs and non-essential comments.', Info, 'Keeps comments that explain behavior, constraints, and public interfaces.'],
  ['whitespace', 'Whitespace & format normalization', 'Collapse blank lines and redundant indentation.', SlidersHorizontal, 'Normalizes low-signal formatting without changing executable content.'],
  ['imports', 'Import consolidation', 'Merge repeated import statements across files.', Sparkles, 'Preserves import meaning while reducing repeated declarations.'],
  ['docstrings', 'Docstring truncation', 'Shorten long docstrings to their first useful line.', Info, 'Keeps the first-line contract and removes verbose historical prose.'],
  ['logs', 'Log statement trimming', 'Remove verbose logging calls from included context.', BarChart3, 'Retains errors and meaningful values while dropping repeated debug noise.'],
  ['tests', 'Test fixture pruning', 'Exclude unrelated test fixtures from the request.', ShieldCheck, 'Keeps fixtures connected to the changed behavior and removes unrelated setup.'],
  ['strings', 'Long string truncation', 'Shorten long string and byte literals in context.', Info, 'Preserves prefixes and structure while eliding payloads that do not inform the task.'],
  ['history', 'Historical diff pruning', 'Drop old diff hunks no longer relevant to the request.', Sparkles, 'Prioritizes the active diff and keeps only history needed to understand intent.'],
]

const MODES = {
  conservative: { label: 'Conservative', icon: ShieldCheck, description: 'Safe trimming with minimal changes.', reduction: 16, risk: 'Very low', color: 'green', badge: '~10–20% reduction' },
  balanced: { label: 'Balanced', icon: Scale, description: 'Smart balance of reduction and fidelity.', reduction: 31, risk: 'Low', color: 'green', badge: '~30–40% reduction' },
  aggressive: { label: 'Aggressive', icon: Zap, description: 'Maximize reduction for high-context requests.', reduction: 46, risk: 'Moderate', color: 'orange', badge: '~45%+ reduction' },
}

function defaultsFor(mode) {
  const enabled = mode === 'conservative' ? ['whitespace', 'imports'] : mode === 'aggressive' ? ALGORITHMS.map(([id]) => id) : ALGORITHMS.filter(([, id]) => !['docstrings', 'strings'].includes(id)).map(([id]) => id)
  return Object.fromEntries(ALGORITHMS.map(([id]) => [id, enabled.includes(id)]))
}

export default function TrimPolicy() {
  const [repo, setRepo] = useState('all repositories')
  const [policy, setPolicy] = useState('balanced')
  const [enabled, setEnabled] = useState(defaultsFor('balanced'))
  const [expanded, setExpanded] = useState(null)
  const [repos, setRepos] = useState([])
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)

  useEffect(() => {
    fetch('/api/repositories').then(response => response.json()).then(data => setRepos(data.repositories || [])).catch(() => setRepos([]))
  }, [])

  function choosePolicy(value) {
    setPolicy(value)
    setEnabled(defaultsFor(value))
  }

  const mode = MODES[policy]
  const enabledCount = Object.values(enabled).filter(Boolean).length
  const reduction = Math.max(0, Math.min(70, Math.round(mode.reduction * (0.7 + enabledCount / ALGORITHMS.length * 0.3))))
  const breakdown = useMemo(() => {
    const weights = { semantic_dedup: 12, stale_context: 7, comment_strip: 5, whitespace: 4, imports: 4, docstrings: 3, logs: 3, tests: 3, strings: 2, history: 3 }
    return ALGORITHMS.filter(([id]) => enabled[id]).map(([id, label]) => ({ id, label, value: Math.max(1, Math.round((weights[id] / 46) * reduction)) })).sort((a, b) => b.value - a.value)
  }, [enabled, reduction])

  async function save() {
    setSaving(true)
    try {
      const writes = [
        ['compression.policy', policy],
        ['compression.policy.scope', repo],
        ...ALGORITHMS.map(([id]) => [`compression.algorithm.${id}.enabled`, String(Boolean(enabled[id]))]),
      ]
      await Promise.all(writes.map(([key, value]) => fetch(`/api/config/${key}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value }) })))
      setSaved(true)
      window.setTimeout(() => setSaved(false), 1800)
    } finally {
      setSaving(false)
    }
  }

  function reset() {
    setPolicy('balanced')
    setEnabled(defaultsFor('balanced'))
    setRepo('all repositories')
  }

  return <main className="policy-page policy-reference">
    <header className="policy-header">
      <div><div className="policy-kicker"><SlidersHorizontal size={14} /> Governance</div><h1>Trim policy</h1><p>Choose how much context TrimPy removes for each repository.</p></div>
      <button className="policy-help-button" onClick={() => setHelpOpen(value => !value)}><Info size={15} /> How trimming works</button>
    </header>
    {helpOpen && <section className="policy-help-panel"><Lightbulb size={17} /><div><b>TrimPy shapes the request before it reaches GitHub Copilot Enterprise.</b><p>It scans for repeated, stale, and low-signal context, preserves structure and safety signals, then records every decision for audit and diff review.</p></div></section>}

    <section className="policy-setup-card">
      <div className="policy-scope-block"><label>Repository scope</label><select value={repo} onChange={event => setRepo(event.target.value)}><option>all repositories</option>{repos.map(item => <option key={item.repository}>{item.repository}</option>)}</select><p>Policy applies to <b>{repo === 'all repositories' ? repos.length : 1} {repo === 'all repositories' ? 'repositories' : 'repository'}</b></p></div>
      <div className="policy-intensity-block"><div className="policy-section-title">Optimization intensity <Info size={14} /></div><div className="policy-modes">{Object.entries(MODES).map(([value, item]) => { const Icon = item.icon; return <button key={value} className={`policy-mode-card ${policy === value ? 'selected' : ''} ${item.color}`} onClick={() => choosePolicy(value)}><span className="policy-mode-icon"><Icon size={17} /></span><span><b>{item.label}</b><small>{item.description}</small><em>{item.badge}</em></span>{policy === value && <span className="policy-mode-check"><Check size={12} /></span>}</button> })}</div></div>
      <aside className="policy-impact-mini"><div className="policy-section-title"><BarChart3 size={15} /> Estimated impact</div><div className="policy-impact-value">{reduction}% <span>Good savings</span></div><div className="policy-progress"><i style={{ width: `${reduction}%` }} /></div><div className="policy-scale"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div><div className="policy-impact-risk"><small>Risk level</small><b className={policy === 'aggressive' ? 'risk-orange' : ''}>{mode.risk}</b></div></aside>
    </section>
    <div className="policy-recommendation"><Info size={15} /><span><b>{mode.label}</b> is selected for {repo}. Customize individual features below before saving.</span></div>

    <section className="policy-content-grid"><section className="policy-features-card"><header><div><h2>Context trimming features</h2><p>Choose which signals TrimPy can shape in this policy.</p></div><span className="policy-enabled-count">{enabledCount}/{ALGORITHMS.length} enabled</span></header><div className="policy-feature-list">{ALGORITHMS.map(([id, label, help, Icon, detail]) => <div className={`policy-feature-row ${expanded === id ? 'expanded' : ''}`} key={id}><div className="policy-feature-main"><span className={`policy-feature-icon ${enabled[id] ? 'on' : ''}`}><Icon size={15} /></span><span><b>{label}</b><small>{help}</small></span></div><div className="policy-feature-actions"><button className={`policy-switch ${enabled[id] ? 'on' : ''}`} role="switch" aria-checked={enabled[id]} aria-label={`${enabled[id] ? 'Disable' : 'Enable'} ${label}`} onClick={() => setEnabled(value => ({ ...value, [id]: !value[id] }))}><i /></button><button className="policy-expand" onClick={() => setExpanded(expanded === id ? null : id)} aria-label={`Explain ${label}`}><ChevronDown size={15} /></button></div>{expanded === id && <div className="policy-feature-detail">{detail} <b>{enabled[id] ? 'Included in requests.' : 'Excluded from requests.'}</b></div>}</div>)}</div><button className="policy-advanced"><SlidersHorizontal size={14} /> Advanced settings <ChevronDown size={14} /></button></section>
      <aside className="policy-impact-rail"><section><div className="policy-section-title"><BarChart3 size={15} /> Estimated impact</div><small>Estimated reduction</small><strong>{reduction}%</strong><span className="policy-good-badge">Good savings</span><div className="policy-progress"><i style={{ width: `${reduction}%` }} /></div><div className="policy-scale"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div></section><section><small>Risk level</small><strong className={policy === 'aggressive' ? 'risk-orange' : ''}>{mode.risk}</strong><p>Safe for coding tasks with traceable decisions.</p></section><section><b>What this policy optimizes</b><ul><li>Removes redundant and stale context</li><li>Preserves review-critical comments</li><li>Maintains code behavior and structure</li><li>Records every applied algorithm</li></ul></section><section className="policy-tip"><Lightbulb size={16} /><b>Tip</b><p>Run the TrimPy benchmark on a real workflow before making an aggressive policy repository-wide.</p><button onClick={() => window.location.hash = '#demo'}>Run benchmark <Zap size={13} /></button></section></aside>
    </section>
    <section className="policy-footer-bar"><button className="policy-reset" onClick={reset}><RotateCcw size={14} /> Reset to defaults</button><button className="policy-save" onClick={save} disabled={saving}><Save size={15} /> {saving ? 'Saving…' : saved ? 'Saved' : 'Save changes'}</button></section>
  </main>
}
