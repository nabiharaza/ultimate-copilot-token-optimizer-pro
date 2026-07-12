import { useEffect, useMemo, useState } from 'react'
import { BookOpen, CheckCircle2, ChevronDown, Clock3, FileText, FlaskConical, Gauge, LockKeyhole, Power, RefreshCw, ShieldCheck, Sparkles, ToggleLeft, ToggleRight, Wrench, Zap } from 'lucide-react'

const DEMO_MESSAGE = `Review the current repository and explain how the request pipeline works. Keep the important constraints, identify the main files, summarize the repeated tool output below, and suggest the safest next steps.

Repository context:
- The service receives requests from several clients and forwards them to a model.
- Preserve authentication, model selection, tool schemas, error handling, and the active diff.
- Explain request tracing, repository detection, token measurement, caching, and response recording.

Repeated tool output:
${Array.from({ length: 80 }, (_, index) => `FAILED check ${index + 1}: timeout while reading an unchanged workspace file; retrying with the same context and the same repository metadata.`).join('\n')}

Please be concise but do not remove security boundaries, exact file references, or actionable implementation details.`

const TEST_CASES = [
  { id: 'tool-output', label: 'Repeated tool output', description: 'Repeated failures and unchanged workspace output.', message: DEMO_MESSAGE },
  { id: 'code-context', label: 'Code context', description: 'Repeated code blocks with stable structure.', message: 'Review this implementation and keep the public behavior, security checks, and error paths.\n\n```python\n' + 'def process_request(data):\n    validated = validate_request(data)\n    result = normalize_payload(validated)\n    return forward_to_model(result)\n'.repeat(90) + '```' },
  { id: 'conversation-history', label: 'Conversation history', description: 'Long repeated assistant and user context.', message: Array.from({ length: 80 }, (_, index) => `User asked for repository context number ${index}. Assistant explained the request flow, the model boundary, the active diff, and the exact next step. Please preserve the decision and continue from the latest request.`).join('\n') },
  { id: 'concise-request', label: 'Concise request', description: 'Small prompt that should remain unchanged.', message: 'Explain the current request path in three bullet points.' },
]

function number(value) { return Number(value || 0).toLocaleString() }
function pct(value) { return `${Number(value || 0).toFixed(2)}%` }
function localTime(value) { return value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—' }
function cleanRepository(value) { return String(value || 'unknown').split(/\r?\n/)[0].trim() || 'unknown' }

export default function LiveTest() {
  const [enabled, setEnabled] = useState(true)
  const [repositories, setRepositories] = useState([])
  const [repository, setRepository] = useState('unassigned')
  const [testCase, setTestCase] = useState(TEST_CASES[0].id)
  const [message, setMessage] = useState(DEMO_MESSAGE)
  const [baseline, setBaseline] = useState(null)
  const [optimized, setOptimized] = useState(null)
  const [running, setRunning] = useState(null)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('Choose a repository and test case, then run the A/B test.')
  const [runHistory, setRunHistory] = useState(() => { try { return JSON.parse(localStorage.getItem('TrimP_test_runs') || '[]') } catch { return [] } })

  const selectedCase = useMemo(() => TEST_CASES.find(item => item.id === testCase) || TEST_CASES[0], [testCase])

  useEffect(() => {
    Promise.all([
      fetch('/api/config').then(response => response.json()),
      fetch('/api/repositories').then(response => response.ok ? response.json() : []),
    ]).then(([config, repositoryPayload]) => {
      const repoRows = Array.isArray(repositoryPayload) ? repositoryPayload : (repositoryPayload.repositories || [])
      setEnabled(String(config['compression.enabled'] ?? 'true') === 'true')
      const cleanedRows = repoRows.map(repo => ({ ...repo, repository: cleanRepository(repo.repository) }))
      setRepositories(cleanedRows)
      if (cleanedRows?.[0]?.repository) setRepository(cleanedRows[0].repository)
    }).catch(() => setStatusMessage('Could not load repository metadata; the test can still run as unassigned.'))
  }, [])

  function chooseCase(value) {
    setTestCase(value)
    const next = TEST_CASES.find(item => item.id === value)
    if (next) setMessage(next.message)
    setBaseline(null)
    setOptimized(null)
  }

  async function setOptimizer(value) {
    setEnabled(value)
    const response = await fetch('/api/config/compression.enabled', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value: String(value) }) })
    setStatusMessage(response.ok ? `TrimPy is now ${value ? 'on and optimizing eligible requests.' : 'off and forwarding requests unchanged.'}` : 'Could not update the TrimPy switch.')
  }

  async function runCase(value) {
    setRunning(value ? 'on' : 'off')
    setError('')
    try {
      const response = await fetch('/api/test/trim', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, enabled: value, repository, test_case: testCase, model: 'gpt-5-mini' }) })
      const result = await response.json()
      if (!response.ok || !result.ok) throw new Error(result.error || 'Test failed')
      if (value) setOptimized(result)
      else setBaseline(result)
      return result
    } catch (cause) {
      setError(cause.message)
      return null
    } finally {
      setRunning(null)
    }
  }

  async function runAB() {
    setStatusMessage(`Running ${selectedCase.label} for ${repository}: off first, then on…`)
    const off = await runCase(false)
    const on = await runCase(true)
    if (!off || !on) return
    const record = {
      id: `${Date.now()}`,
      created_at: new Date().toISOString(),
      repository,
      test_case: selectedCase.label,
      before: off.stats.tokens_before,
      baseline_after: off.stats.tokens_after,
      optimized_after: on.stats.tokens_after,
      saved: Math.max(0, Number(off.stats.tokens_after || 0) - Number(on.stats.tokens_after || 0)),
      reduction: on.stats.savings_pct,
      grade: on.quality.grade,
      algorithms: [...new Set((on.stats.changes || []).map(change => change.method))],
    }
    setRunHistory(previous => { const next = [record, ...previous].slice(0, 20); localStorage.setItem('TrimP_test_runs', JSON.stringify(next)); return next })
    setStatusMessage(`A/B test complete and documented for ${repository}.`)
  }

  return <main className="live-test-page">
    <header className="live-test-header"><div><div className="conversation-kicker"><FlaskConical size={15} /> Evidence lab</div><h1>Test TrimPy live</h1><p>Run repeatable A/B cases by repository and keep a local record of what happened.</p></div><div className="live-test-header-actions"><button className="test-button primary" onClick={runAB} disabled={!!running}><Sparkles size={15} /> {running ? 'Testing…' : 'One-click A/B test'}</button><div className={`optimizer-switch ${enabled ? 'is-on' : 'is-off'}`}><span className="optimizer-switch-label"><Power size={15} /> TrimPy {enabled ? 'on' : 'off'}</span><button onClick={() => setOptimizer(!enabled)} aria-label={`Turn TrimPy ${enabled ? 'off' : 'on'}`} title={`Turn TrimPy ${enabled ? 'off' : 'on'}`}>{enabled ? <ToggleRight size={30} /> : <ToggleLeft size={30} />}</button></div></div></header>

    <section className="live-test-notice"><ShieldCheck size={18} /><div><b>Safe local test</b><span>This test measures the request body only. It does not contact GitHub or consume Copilot quota.</span><small>{statusMessage}</small></div><LockKeyhole size={16} /></section>
    <section className="test-selection-bar"><label><span><GitRepoIcon /> Repository</span><select value={repository} onChange={event => setRepository(event.target.value)}><option value="unassigned">Unassigned / local test</option>{repositories.map(repo => <option key={repo.repository} value={repo.repository}>{repo.repository}</option>)}</select></label><label><span><FlaskConical size={14} /> Test case</span><select value={testCase} onChange={event => chooseCase(event.target.value)}>{TEST_CASES.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><div className="test-case-description"><b>{selectedCase.label}</b><span>{selectedCase.description}</span></div></section>

    <section className="live-test-layout"><div className="live-test-input glass-card"><div className="live-test-section-heading"><div><h2>Chat message to test</h2><p>Edit the selected case or restore its documented default.</p></div><button className="icon-button" onClick={() => setMessage(selectedCase.message)} title="Restore selected test case"><RefreshCw size={15} /></button></div><textarea value={message} onChange={event => setMessage(event.target.value)} /><div className="live-test-actions"><button className="test-button baseline" onClick={() => runCase(false)} disabled={!!running}><Power size={15} /> Run off only</button><button className="test-button optimized" onClick={() => runCase(true)} disabled={!!running}><Zap size={15} /> Run on only</button><button className="test-button primary" onClick={runAB} disabled={!!running}><Sparkles size={15} /> Run documented A/B</button></div>{error && <div className="live-test-error">{error}</div>}</div><div className="live-test-explainer glass-card"><div className="live-test-section-heading"><div><h2>How this is verified</h2><p>Every run follows the same calculation.</p></div><Gauge size={19} /></div><ol><li><b>Off baseline</b><span>Optimizer bypassed; before and after must match.</span></li><li><b>On comparison</b><span>Same repository, case, model, and message are optimized.</span></li><li><b>Delta</b><span>Saved = baseline after − optimized after.</span></li><li><b>Evidence</b><span>Repository, timestamp, grade, and algorithms are recorded below.</span></li></ol><small>These are local request preflight signals. Actual model answer quality requires an upstream Copilot comparison.</small></div></section>
    <section className="live-test-results"><TestResult title="TrimPy off · baseline" icon={Power} result={baseline} muted /><TestResult title="TrimPy on · optimized" icon={Zap} result={optimized} /><Comparison baseline={baseline} optimized={optimized} /></section>
    <TestHistory rows={runHistory} onClear={() => { localStorage.removeItem('TrimP_test_runs'); setRunHistory([]) }} />
  </main>
}

function GitRepoIcon() { return <Wrench size={14} /> }

function TestResult({ title, icon: Icon, result, muted }) {
  return <article className={`test-result-card glass-card ${muted ? 'muted-result' : ''}`}><header><span className="test-result-icon"><Icon size={17} /></span><div><b>{title}</b><small>{result ? `${result.quality.grade} preflight grade · ${result.repository} · ${result.test_case}` : 'Run this case to populate the evidence'}</small></div></header>{result ? <div className="test-metrics"><Metric label="Before" value={number(result.stats.tokens_before)} /><Metric label="After" value={number(result.stats.tokens_after)} /><Metric label="Saved" value={number(result.stats.tokens_saved)} good /><Metric label="Reduction" value={pct(result.stats.savings_pct)} good /><Metric label="Context kept" value={pct(result.quality.context_preservation)} /></div> : <div className="test-result-empty">Waiting for a test run.</div>}</article>
}

function Metric({ label, value, good }) { return <div><span>{label}</span><b className={good ? 'good' : ''}>{value}</b></div> }

function Comparison({ baseline, optimized }) {
  if (!baseline || !optimized) return <article className="test-comparison-card glass-card"><CheckCircle2 size={18} /><div><b>Run both cases to see the measured difference</b><span>The comparison will show exactly how many estimated tokens TrimPy removes.</span></div></article>
  const saved = Math.max(0, Number(baseline.stats.tokens_after || 0) - Number(optimized.stats.tokens_after || 0))
  return <article className="test-comparison-card glass-card"><span className="comparison-orb"><Sparkles size={19} /></span><div><b>A/B result: {number(saved)} fewer estimated tokens with TrimPy on</b><span>{pct(optimized.stats.savings_pct)} reduction from the original request. Context preservation scored {pct(optimized.quality.context_preservation)} and structure remained intact.</span></div></article>
}

function TestHistory({ rows, onClear }) {
  return <section className="test-history glass-card"><header><div><h2><BookOpen size={17} /> Test run evidence</h2><p>Local documentation of what was tested and how TrimPy calculated the result.</p></div><button className="clear-history-button" onClick={onClear}>Clear history</button></header>{rows.length ? <div className="test-history-table"><div className="test-history-row test-history-head"><span>Time</span><span>Repository</span><span>Case</span><span>Saved</span><span>Grade</span><span>Algorithms</span></div>{rows.map(row => <div className="test-history-row" key={row.id}><span><Clock3 size={13} />{localTime(row.created_at)}</span><span>{row.repository}</span><span>{row.test_case}</span><span className="good">{number(row.saved)} · {pct(row.reduction)}</span><span className="history-grade">{row.grade}</span><span>{row.algorithms.length ? row.algorithms.join(', ') : 'No changes'}</span></div>)}</div> : <div className="test-history-empty">No documented runs yet. Choose a repository, select a case, and click One-click A/B test.</div>}</section>
}
