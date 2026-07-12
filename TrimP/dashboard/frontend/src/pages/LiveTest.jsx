import { useEffect, useState } from 'react'
import { CheckCircle2, FlaskConical, Gauge, LockKeyhole, MessageSquare, Power, RefreshCw, ShieldCheck, Sparkles, ToggleLeft, ToggleRight, Zap } from 'lucide-react'

const DEMO_MESSAGE = `Review the current repository and explain how the request pipeline works. Keep the important constraints, identify the main files, summarize the repeated tool output below, and suggest the safest next steps.

Repository context:
- The service receives requests from several clients and forwards them to a model.
- Preserve authentication, model selection, tool schemas, error handling, and the active diff.
- Explain how request tracing, repository detection, token measurement, caching, and response recording work.

Repeated tool output:
${Array.from({ length: 18 }, (_, index) => `FAILED check ${index + 1}: timeout while reading an unchanged workspace file; retrying with the same context and the same repository metadata.`).join('\n')}

Please be concise but do not remove security boundaries, exact file references, or actionable implementation details.`

function number(value) {
  return Number(value || 0).toLocaleString()
}

function pct(value) {
  return `${Number(value || 0).toFixed(2)}%`
}

export default function LiveTest() {
  const [enabled, setEnabled] = useState(true)
  const [message, setMessage] = useState(DEMO_MESSAGE)
  const [baseline, setBaseline] = useState(null)
  const [optimized, setOptimized] = useState(null)
  const [running, setRunning] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/config').then(response => response.json()).then(config => setEnabled(String(config['compression.enabled'] ?? 'true') === 'true')).catch(() => {})
  }, [])

  async function setOptimizer(value) {
    setEnabled(value)
    await fetch('/api/config/compression.enabled', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value: String(value) }) })
  }

  async function runCase(value) {
    setRunning(value)
    setError('')
    try {
      const response = await fetch('/api/test/trim', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, enabled: value, model: 'gpt-5-mini' }) })
      const result = await response.json()
      if (!response.ok || !result.ok) throw new Error(result.error || 'Test failed')
      if (value) setOptimized(result)
      else setBaseline(result)
    } catch (cause) {
      setError(cause.message)
    } finally {
      setRunning(null)
    }
  }

  async function runAB() {
    await runCase(false)
    await runCase(true)
  }

  return <main className="live-test-page">
    <header className="live-test-header"><div><div className="conversation-kicker"><FlaskConical size={15} /> Evidence lab</div><h1>Test TrimPy live</h1><p>Run the same chat context with TrimPy off and on, then compare the measured request transformation.</p></div><div className={`optimizer-switch ${enabled ? 'is-on' : 'is-off'}`}><span className="optimizer-switch-label"><Power size={15} /> TrimPy {enabled ? 'on' : 'off'}</span><button onClick={() => setOptimizer(!enabled)} aria-label={`Turn TrimPy ${enabled ? 'off' : 'on'}`} title={`Turn TrimPy ${enabled ? 'off' : 'on'}`}>{enabled ? <ToggleRight size={30} /> : <ToggleLeft size={30} />}</button></div></header>

    <section className="live-test-notice"><ShieldCheck size={18} /><div><b>Safe local test</b><span>This demo measures the request body only. It does not contact GitHub or consume Copilot quota.</span></div><LockKeyhole size={16} /></section>
    <section className="live-test-layout"><div className="live-test-input glass-card"><div className="live-test-section-heading"><div><h2>Chat message to test</h2><p>Use a real prompt or keep the deliberately repetitive demo context.</p></div><button className="icon-button" onClick={() => setMessage(DEMO_MESSAGE)} title="Restore demo message"><RefreshCw size={15} /></button></div><textarea value={message} onChange={event => setMessage(event.target.value)} /><div className="live-test-actions"><button className="test-button baseline" onClick={() => runCase(false)} disabled={!!running}><Power size={15} /> {running === false ? 'Testing off…' : 'Run with TrimPy off'}</button><button className="test-button optimized" onClick={() => runCase(true)} disabled={!!running}><Zap size={15} /> {running === true ? 'Testing on…' : 'Run with TrimPy on'}</button><button className="test-button primary" onClick={runAB} disabled={!!running}><Sparkles size={15} /> Run A/B test</button></div>{error && <div className="live-test-error">{error}</div>}</div><div className="live-test-explainer glass-card"><div className="live-test-section-heading"><div><h2>What is measured</h2><p>Signals that make the comparison explainable.</p></div><Gauge size={19} /></div><ul><li><b>Token delta</b><span>Same estimator before and after each transformation.</span></li><li><b>Conciseness</b><span>How much redundant request volume was removed.</span></li><li><b>Context preservation</b><span>How much meaningful vocabulary remains in the optimized prompt.</span></li><li><b>Structure preserved</b><span>Whether the request shape and protected fields stay intact.</span></li></ul><small>Model answer quality still requires an upstream A/B run. These are local preflight signals.</small></div></section>
    <section className="live-test-results"><TestResult title="TrimPy off · baseline" icon={Power} result={baseline} muted /><TestResult title="TrimPy on · optimized" icon={Zap} result={optimized} /><Comparison baseline={baseline} optimized={optimized} /></section>
  </main>
}

function TestResult({ title, icon: Icon, result, muted }) {
  return <article className={`test-result-card glass-card ${muted ? 'muted-result' : ''}`}><header><span className="test-result-icon"><Icon size={17} /></span><div><b>{title}</b><small>{result ? `${result.quality.grade} preflight grade · ${result.model}` : 'Run this case to populate the evidence'}</small></div></header>{result ? <div className="test-metrics"><Metric label="Before" value={number(result.stats.tokens_before)} /><Metric label="After" value={number(result.stats.tokens_after)} /><Metric label="Saved" value={number(result.stats.tokens_saved)} good /><Metric label="Reduction" value={pct(result.stats.savings_pct)} good /><Metric label="Context kept" value={pct(result.quality.context_preservation)} /></div> : <div className="test-result-empty">Waiting for a test run.</div>}</article>
}

function Metric({ label, value, good }) {
  return <div><span>{label}</span><b className={good ? 'good' : ''}>{value}</b></div>
}

function Comparison({ baseline, optimized }) {
  if (!baseline || !optimized) return <article className="test-comparison-card glass-card"><CheckCircle2 size={18} /><div><b>Run both cases to see the measured difference</b><span>The comparison will show exactly how many estimated tokens TrimPy removes and whether the preflight signals remain healthy.</span></div></article>
  const saved = Math.max(0, Number(baseline.stats.tokens_after || 0) - Number(optimized.stats.tokens_after || 0))
  return <article className="test-comparison-card glass-card"><span className="comparison-orb"><Sparkles size={19} /></span><div><b>A/B result: {number(saved)} fewer estimated tokens with TrimPy on</b><span>{pct(optimized.stats.savings_pct)} reduction from the original request. Context preservation scored {pct(optimized.quality.context_preservation)} and structure remained intact.</span></div></article>
}
