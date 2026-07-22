import { useMemo, useState } from 'react'
import {
  Activity, ArrowRight, BookOpen, Braces, CheckCircle2, ChevronRight,
  CircleHelp, Code2, Database, FileCode2, FileText, Gauge, GitBranch, History,
  Layers3, Lock, Network, Play, Radio, RotateCcw, Search, Server, ShieldCheck,
  Sparkles, Terminal, UserRound, Workflow, Wrench, Zap,
} from 'lucide-react'

const GUIDES = [
  { id: 'developer', title: 'Developer documentation', short: 'Developer', description: 'Compiler internals, algorithms, APIs, verification, and live request planning.', icon: Code2, badge: 'Technical' },
  { id: 'user', title: 'User documentation', short: 'User guide', description: 'Installation, editor connections, daily operation, policies, and troubleshooting.', icon: BookOpen, badge: 'Operate' },
  { id: 'architecture', title: 'Architecture & data flow', short: 'Architecture', description: 'Trust boundaries, runtime topology, sequence flow, and failure behavior.', icon: Network, badge: 'System' },
  { id: 'changelog', title: 'Release changelog', short: 'Changelog', description: 'Versioned product, safety, algorithm, dashboard, and operational changes.', icon: History, badge: '1.1.0' },
]

const STAGES = [
  { id: 'client', title: 'Client & IDE', icon: UserRound, layer: 'Input', detail: 'VS Code, JetBrains IDEs, or Copilot CLI creates an authenticated request and remains responsible for model selection.', input: 'Prompt, history, repository context, tools, model', output: 'Authenticated request envelope', invariant: 'Client authentication is never replaced by TrimPy.' },
  { id: 'intercept', title: 'Local interception', icon: Server, layer: 'Edge', detail: 'The localhost proxy accepts the request, attaches local repository/IDE provenance, and identifies the API protocol.', input: 'HTTP request and local source metadata', output: 'Parsed request object', invariant: 'Unsupported shapes remain forwardable.' },
  { id: 'intent', title: 'Intent & ledger', icon: FileCode2, layer: 'Understand', detail: 'The latest task becomes an auditable intent contract while each context unit receives a type, hash, risk, protection, and provenance record.', input: 'Messages, Responses items, tools, instructions', output: 'Intent contract and typed context ledger', invariant: 'The original latest-user request remains verbatim.' },
  { id: 'retrieve', title: 'Retrieve & budget', icon: Search, layer: 'Select', detail: 'Tenant-authorized chunks are ranked using BM25, identifiers, structure, boundary context, recency, and diversity before a token budget is applied.', input: 'Authorized context chunks and current query', output: 'Smallest relevant evidence set', invariant: 'Authorization is evaluated before scoring.' },
  { id: 'shape', title: 'Risk-routed compression', icon: Activity, layer: 'Transform', detail: 'Code, JSON, logs, search output, conversation history, and prose use different structural or learned algorithms.', input: 'Typed eligible context units', output: 'Candidate replacements with attribution', invariant: 'Protected protocol fields are never sent to a lossy algorithm.' },
  { id: 'verify', title: 'Verify, repair, or restore', icon: ShieldCheck, layer: 'Assure', detail: 'Task-named and diagnostic anchors, constraints, schemas, syntax, latest-user intent, tools, and opaque protocol objects are checked after every lossy edit. Missing critical values are compactly reinserted before restoration is considered.', input: 'Original and candidate values', output: 'Accepted candidate, repaired candidate, or restored original', invariant: 'A failed gate is a safe fallback, not a broken request.' },
  { id: 'upstream', title: 'Provider boundary', icon: GitBranch, layer: 'Forward', detail: 'The optimized request is assembled for provider caching and forwarded with the original client authentication and model choice.', input: 'Verified request body', output: 'Provider response and exposed usage', invariant: 'Provider usage is billing truth.' },
  { id: 'trace', title: 'Evidence & dashboard', icon: Database, layer: 'Observe', detail: 'Hashes, field paths, algorithms, verification, fallbacks, tokenizer provenance, repository, IDE, and actual usage are written locally.', input: 'Compiler and provider decision records', output: 'Diff review, validation, and manager proof', invariant: 'Zero samples display as not measured.' },
]

const ALGORITHMS = [
  { id: 'conversation', title: 'Conversation state', type: 'History', icon: Workflow, route: 'Task-state-v1 + BM25 + verbatim tail', target: '55–70%', safety: 'No role escalation; latest turns remain unchanged', verifier: 'Latest-user and payload contract' },
  { id: 'lingua', title: 'LLMLingua-2', type: 'Prose', icon: Sparkles, route: 'Shared, asynchronously warmed Microsoft token classifier', target: 'Policy + latency budget', safety: 'Default-on; complete-unit extractive fail-open', verifier: 'Critical anchors, constraints, non-empty output' },
  { id: 'retrieval', title: 'Query retriever', type: 'Corpus', icon: Search, route: 'BM25 + identifiers + structure + diversity', target: 'Token budget', safety: 'Tenant/principal authorization before rank', verifier: 'Original source remains reconstructable' },
  { id: 'code', title: 'Code context trimmer', type: 'Code', icon: Code2, route: 'Deduplication + AST-aware structural selection', target: '40–70%', safety: 'Imports, signatures, symbols, and public structure', verifier: 'Protected symbols and syntax' },
  { id: 'json', title: 'JSON minimizer', type: 'Structured', icon: Braces, route: 'Structural minification + bounded repeated rows', target: '30–55%', safety: 'No string-level semantic rewriting', verifier: 'Parse validity and top-level keys' },
  { id: 'logs', title: 'Error-centered logs', type: 'Logs', icon: Terminal, route: 'Error clusters + stack traces + edge samples', target: '60–95%', safety: 'Keeps failures, paths, codes, quantities, exits', verifier: 'Concrete diagnostic anchors' },
  { id: 'search', title: 'Search result reducer', type: 'Search', icon: FileText, route: 'File grouping + match deduplication', target: '70–95%', safety: 'Retains file attribution and representative matches', verifier: 'Path anchors' },
  { id: 'prompt', title: 'Exact duplicate reducer', type: 'Prompt', icon: Layers3, route: 'Duplicate block/line removal only', target: 'Input-dependent', safety: 'No stop-word deletion or broad regex rewriting', verifier: 'Constraints and anchor retention' },
]

const DEMO_INPUT = `Summarize the failing checks below. Preserve src/payment/api.py, HTTP 503, retry_count=3, and the instruction: do not modify production data.

Captured CI log:
${Array.from({ length: 24 }, (_, index) => `2026-07-21 12:${String(index).padStart(2, '0')}:00 ERROR HTTP 503 in src/payment/api.py retry_count=3 unchanged dependency timeout; retrying identical operation`).join('\n')}
2026-07-21 12:25:00 FATAL HTTP 503 in src/payment/api.py after retry_count=3; deployment stopped.`

const USER_STEPS = [
  ['Install and diagnose', 'Create a virtual environment, install TrimPy, then initialize and diagnose it.', 'python3 -m venv .venv\nsource .venv/bin/activate\npip install -e .\ntrimp init\ntrimp doctor'],
  ['Start both services', 'The dashboard is the control plane; the proxy is the request path.', 'trimp dashboard --mode web --port 7432 --no-browser\ntrimp proxy start --port 8765'],
  ['Connect your editor', 'Configure the editor, restart it completely, and start the local evidence monitor.', 'trimp vscode configure\ntrimp intellij configure\ntrimp monitor --mode editors --daemon'],
  ['Prove the path', 'Send one fixed prompt off and on, inspect its Diff review, then run Validation.', 'trimp quick\ntrimp monitor --mode editor-status'],
]

const PRODUCT_TOUR = [
  ['Dashboard', 'Health, traffic, reduction, model mix, and recent work'],
  ['Repositories', 'Repository-level volume, savings, IDE, branch, and model attribution'],
  ['Trim policy', 'Choose policy and inspect algorithm controls'],
  ['Conversations', 'Search complete request histories and usage evidence'],
  ['A/B preflight', 'Local off/on request-body comparison without model spend'],
  ['Validation', 'Repeatable preservation, latency, audit, and fail-open evidence'],
  ['Diff review', 'Exact kept, removed, and modified context for one request'],
]

const RELEASES = [
  { version: 'Unreleased', date: 'In development', tone: 'current', summary: 'Documentation becomes an operational product surface.', groups: [
    ['Added', ['Developer, User, Architecture, and Changelog guides', 'Embedded policy-aware compression laboratory', 'Interactive compiler stages, algorithms, trust boundaries, and failure matrix']],
    ['Fixed', ['Restored the complete /api/test/trim route', 'Added request-level policy selection to local planning APIs', 'Replaced per-request JetBrains processes with a persistent warmed optimizer worker', 'Made critical-anchor verification query-aware with compact reinsertion', 'Separated sent-payload retention from rejected-candidate diagnostics']],
  ] },
  { version: '1.1.0', date: 'July 21, 2026', tone: 'released', summary: 'Evidence-preserving context compiler and manager proof.', groups: [
    ['Added', ['Typed context ledger and correction-aware intent contracts', 'Authorization-first retrieval and structured conversation state', 'Default-on Microsoft LLMLingua-2 with verified fallback', 'Anchor, syntax, schema, payload, and protocol verification', 'Provider-aware token/cache accounting and manager quality metrics']],
    ['Changed', ['Retired unsafe stop-word and word-frequency pruning', 'Made exact duplicate removal the only general prompt rewrite', 'Separated local estimates from actual provider usage']],
    ['Security', ['Protected instructions, latest task, tools, call IDs, and opaque protocol state', 'Added injection signals and untrusted tool-data boundaries']],
  ] },
  { version: '1.0.0', date: 'July 1, 2026', tone: 'released', summary: 'Initial local proxy, CLI, audit database, and evidence dashboard.', groups: [
    ['Added', ['CLI and local compression proxy', 'SQLite audit history', 'Repository, conversation, policy, validation, and diff surfaces']],
  ] },
]

function number(value) { return Number(value || 0).toLocaleString() }
function percent(value) { return `${Number(value || 0).toFixed(1)}%` }

export default function SystemDesign() {
  const storedGuide = localStorage.getItem('TrimP_docs_guide')
  const [guide, setGuide] = useState(GUIDES.some(item => item.id === storedGuide) ? storedGuide : 'developer')
  const activeGuide = GUIDES.find(item => item.id === guide) || GUIDES[0]
  const ActiveGuideIcon = activeGuide.icon

  function chooseGuide(next) {
    setGuide(next)
    localStorage.setItem('TrimP_docs_guide', next)
    document.querySelector('.main-content')?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return <main className="docs-hub">
    <header className="docs-hero">
      <div className="docs-hero-copy">
        <div className="docs-kicker"><BookOpen size={15} /> TrimPy knowledge system <span>v1.1.0</span></div>
        <h1>Technical clarity from first request to final proof.</h1>
        <p>Operate TrimPy confidently, inspect its compiler internals, and explain every context decision with durable engineering evidence.</p>
        <div className="docs-hero-pills"><span><ShieldCheck size={14} /> Fail-open by contract</span><span><Database size={14} /> Local evidence</span><span><Sparkles size={14} /> LLMLingua-2 enabled</span></div>
      </div>
      <div className="docs-hero-system" aria-label="Documentation status">
        <div><small>Current release</small><strong>1.1.0</strong><span>Context compiler</span></div>
        <div><small>Protected target</small><strong>100%</strong><span>Anchor retention</span></div>
        <div><small>Guides</small><strong>4</strong><span>One source of truth</span></div>
      </div>
    </header>

    <nav className="docs-guide-tabs" aria-label="Documentation guides">
      {GUIDES.map(item => { const Icon = item.icon; return <button type="button" key={item.id} className={guide === item.id ? 'active' : ''} onClick={() => chooseGuide(item.id)}><span><Icon size={18} /></span><div><b>{item.title}</b><small>{item.description}</small></div><mark>{item.badge}</mark><ChevronRight size={15} /></button> })}
    </nav>

    <div className="docs-layout">
      <aside className="docs-rail">
        <div className="docs-rail-title"><ActiveGuideIcon size={16} /><span><small>Reading</small><b>{activeGuide.short}</b></span></div>
        <div className="docs-outline">
          {(guide === 'developer' ? ['Engineering contract', 'Compiler lifecycle', 'Compression algorithms', 'Working laboratory', 'Local APIs'] : guide === 'user' ? ['Quick start', 'Operate TrimPy', 'Choose a policy', 'Manager proof', 'Troubleshooting'] : guide === 'architecture' ? ['System topology', 'Request pipeline', 'Trust boundaries', 'Failure behavior', 'Observability'] : ['Unreleased', '1.1.0', '1.0.0', 'Release discipline']).map((item, index) => <span key={item}><i>{String(index + 1).padStart(2, '0')}</i>{item}</span>)}
        </div>
        <div className="docs-source-card"><FileText size={16} /><div><b>Durable source</b><small>{guide === 'developer' ? 'docs/DEVELOPER_GUIDE.md' : guide === 'user' ? 'docs/USER_GUIDE.md' : guide === 'architecture' ? 'docs/ARCHITECTURE_GUIDE.md' : 'CHANGELOG.md'}</small></div></div>
      </aside>
      <section className="docs-reader">
        {guide === 'developer' && <DeveloperGuide />}
        {guide === 'user' && <UserGuide onNavigate={chooseGuide} />}
        {guide === 'architecture' && <ArchitectureGuide />}
        {guide === 'changelog' && <ChangelogGuide />}
      </section>
    </div>
  </main>
}

function DocHeading({ eyebrow, title, children, icon: Icon }) {
  return <header className="docs-reader-heading"><div className="docs-reader-icon"><Icon size={22} /></div><div><span>{eyebrow}</span><h2>{title}</h2><p>{children}</p></div></header>
}

function DeveloperGuide() {
  const [activeAlgorithm, setActiveAlgorithm] = useState(ALGORITHMS[1].id)
  const algorithm = ALGORITHMS.find(item => item.id === activeAlgorithm) || ALGORITHMS[0]
  const AlgorithmIcon = algorithm.icon
  return <div className="docs-document">
    <DocHeading eyebrow="Developer documentation" title="Build against the compiler contract" icon={Code2}>A technical guide to the request compiler, selection algorithms, verification gates, provider boundary, and local APIs.</DocHeading>
    <section className="docs-invariant-banner"><Lock size={19} /><div><b>The engineering invariant</b><p>Reduce eligible evidence—not control state. Every lossy candidate is verified, attributed, and either accepted or replaced with its original.</p></div><code>retrieve → transform → verify → accept | restore</code></section>

    <section className="docs-section">
      <SectionTitle index="01" title="Compiler lifecycle" subtitle="One request, ten explicit decisions" />
      <div className="docs-lifecycle">{STAGES.slice(0, 6).map((stage, index) => { const Icon = stage.icon; return <article key={stage.id}><span>{index + 1}</span><Icon size={17} /><b>{stage.title}</b><small>{stage.layer}</small>{index < 5 && <ArrowRight size={14} />}</article> })}</div>
      <div className="docs-contract-grid">
        <article><b>Protected</b><p>System/developer messages, latest-user directive, tools, model, response format, call IDs, encrypted reasoning, item references.</p></article>
        <article><b>Eligible</b><p>Historical turns, repeated tool output, logs, JSON rows, duplicate code blocks, search results, and long supporting prose.</p></article>
        <article><b>Recorded</b><p>Field path, type, risk, tokenizer, before/after counts, method, confidence, anchors, checks, fallback reason, provider plan.</p></article>
      </div>
    </section>

    <section className="docs-section">
      <SectionTitle index="02" title="Compression algorithm registry" subtitle="Routing is based on content type and risk—not one universal text trick" />
      <div className="algorithm-browser">
        <div className="algorithm-list">{ALGORITHMS.map(item => { const Icon = item.icon; return <button type="button" className={activeAlgorithm === item.id ? 'active' : ''} key={item.id} onClick={() => setActiveAlgorithm(item.id)}><Icon size={16} /><span><b>{item.title}</b><small>{item.type}</small></span><ChevronRight size={14} /></button> })}</div>
        <article className="algorithm-detail"><div className="algorithm-detail-head"><span><AlgorithmIcon size={20} /></span><div><small>{algorithm.type} route</small><h3>{algorithm.title}</h3></div><mark>{algorithm.target}</mark></div><dl><div><dt>Technique</dt><dd>{algorithm.route}</dd></div><div><dt>Safety boundary</dt><dd>{algorithm.safety}</dd></div><div><dt>Acceptance gate</dt><dd>{algorithm.verifier}</dd></div></dl><div className="algorithm-decision"><CheckCircle2 size={15} /> Candidate is forwarded only after verification; otherwise the original unit is restored.</div></article>
      </div>
    </section>

    <CompressionLab />

    <section className="docs-section">
      <SectionTitle index="04" title="Local API surface" subtitle="Plan and test request shaping without contacting a model" />
      <div className="docs-api-grid"><article><span className="method post">POST</span><code>/api/context/plan</code><p>Returns the optimized request, intent contract, context ledger, provider plan, changes, verification, and fallbacks.</p></article><article><span className="method post">POST</span><code>/api/test/trim</code><p>Runs a local off/on-compatible request-body demonstration with token, quality, algorithm, and preservation evidence.</p></article><article><span className="method get">GET</span><code>/api/validation/proof-report</code><p>Combines release validation, measured value, live evidence, and runtime context-quality signals for management review.</p></article></div>
      <CodeBlock>{`from TrimP.chat_optimizer import ChatPayloadOptimizer\n\noptimized, stats = ChatPayloadOptimizer(policy="balanced").optimize_body(\n    request_body, enabled=True\n)\nassert stats.protected_anchor_retention_pct == 100.0`}</CodeBlock>
    </section>
  </div>
}

function CompressionLab() {
  const [message, setMessage] = useState(DEMO_INPUT)
  const [policy, setPolicy] = useState('balanced')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const methods = useMemo(() => [...new Set((result?.stats?.changes || []).map(item => item.method))], [result])

  async function run() {
    setRunning(true)
    setError('')
    try {
      const response = await fetch('/api/test/trim', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, enabled: true, policy, model: 'gpt-5-mini', repository: 'documentation-lab', test_case: 'developer-docs' }) })
      const payload = await response.json()
      if (!response.ok || !payload.ok) throw new Error(payload.error || 'The local compression test failed.')
      setResult(payload)
    } catch (cause) {
      setError(cause.message)
    } finally {
      setRunning(false)
    }
  }

  return <section className="docs-section docs-lab">
    <div className="docs-lab-heading"><SectionTitle index="03" title="Working compression laboratory" subtitle="Runs locally through the real request optimizer; no upstream model call" /><div className="docs-lab-status"><Radio size={13} /><span>Local-only</span></div></div>
    <div className="docs-lab-controls"><label><span>Policy</span><select value={policy} onChange={event => setPolicy(event.target.value)}><option value="conservative">Conservative</option><option value="balanced">Balanced</option><option value="aggressive">Aggressive</option></select></label><button type="button" className="docs-run-button" onClick={run} disabled={running || !message.trim()}><Play size={15} /> {running ? 'Compiling…' : 'Run context compiler'}</button><button type="button" className="docs-reset-button" onClick={() => { setMessage(DEMO_INPUT); setResult(null); setError('') }}><RotateCcw size={14} /> Reset</button></div>
    <div className="docs-lab-editor"><div className="docs-lab-pane"><header><span>01</span><b>Original request</b><small>Editable fixture</small></header><textarea aria-label="Compression demo input" value={message} onChange={event => setMessage(event.target.value)} /></div><div className="docs-lab-pane output"><header><span>02</span><b>Verified output</b><small>{result ? 'Candidate accepted or safely restored' : 'Run the compiler to inspect output'}</small></header><pre>{result?.optimized_message || 'The optimized request will appear here with its evidence record.'}</pre></div></div>
    {error && <div className="docs-lab-error"><CircleHelp size={15} /> {error}</div>}
    {result && <div className="docs-lab-evidence" aria-live="polite"><div><small>Before</small><b>{number(result.stats.tokens_before)}</b><span>{result.stats.tokenizer}</span></div><div><small>After</small><b>{number(result.stats.tokens_after)}</b><span>{result.stats.token_count_exact ? 'exact local count' : 'labeled estimate'}</span></div><div className="good"><small>Reduction</small><b>{percent(result.stats.savings_pct)}</b><span>{number(result.stats.tokens_saved)} tokens removed</span></div><div><small>Anchor retention</small><b>{percent(result.stats.protected_anchor_retention_pct)}</b><span>{result.stats.fallbacks?.length || 0} safe fallbacks</span></div><div className="docs-lab-methods"><small>Accepted algorithms</small><p>{methods.length ? methods.map(method => <mark key={method}>{method}</mark>) : <span>No lossy change accepted</span>}</p></div></div>}
    <p className="docs-lab-footnote"><Lock size={13} /> This measures the serialized request locally. Provider response usage remains the billing source of truth.</p>
  </section>
}

function UserGuide({ onNavigate }) {
  const [step, setStep] = useState(0)
  return <div className="docs-document">
    <DocHeading eyebrow="User documentation" title="Operate TrimPy with confidence" icon={BookOpen}>A practical path from installation to an inspectable, defensible off/on comparison.</DocHeading>
    <section className="docs-section"><SectionTitle index="01" title="Quick start" subtitle="Four checkpoints to a working local setup" /><div className="user-quickstart"><div className="user-step-list">{USER_STEPS.map((item, index) => <button type="button" key={item[0]} className={step === index ? 'active' : ''} onClick={() => setStep(index)}><span>{index + 1}</span><div><b>{item[0]}</b><small>{item[1]}</small></div><ChevronRight size={15} /></button>)}</div><div className="user-step-detail"><span>Step {step + 1} of {USER_STEPS.length}</span><h3>{USER_STEPS[step][0]}</h3><p>{USER_STEPS[step][1]}</p><CodeBlock>{USER_STEPS[step][2]}</CodeBlock></div></div></section>
    <section className="docs-section"><SectionTitle index="02" title="Product tour" subtitle="Use each surface for one clear evidence question" /><div className="user-tour-grid">{PRODUCT_TOUR.map(([title, description], index) => <article key={title}><span>{String(index + 1).padStart(2, '0')}</span><b>{title}</b><p>{description}</p></article>)}</div></section>
    <section className="docs-section"><SectionTitle index="03" title="Choose a policy" subtitle="Protection is constant; only the reduction target changes" /><div className="policy-guide-grid"><article><span>01</span><h3>Conservative</h3><b>Highest preservation threshold</b><p>Use for unfamiliar repositories, sensitive changes, and early rollout.</p></article><article className="recommended"><span>02 · Recommended</span><h3>Balanced</h3><b>Daily engineering default</b><p>Strong verified reduction without chasing maximum compression.</p></article><article><span>03</span><h3>Aggressive</h3><b>Large repetitive contexts</b><p>Use after validation for long logs, searches, or histories.</p></article></div></section>
    <section className="docs-section"><SectionTitle index="04" title="Management proof" subtitle="Show trust and value as separate evidence" /><div className="manager-proof-guide"><div><Gauge size={20} /><h3>Five controlled cases</h3><p>Repeat one fixed prompt across long history, repeated tool output, code, multiple files, and a concise request.</p></div><ol><li>Send the prompt once with TrimPy off.</li><li>Send the exact prompt with TrimPy on.</li><li>Keep model, IDE, repository, and context fixed.</li><li>Inspect Diff review, verification, and actual usage.</li><li>Run Validation before claiming rollout readiness.</li></ol><button type="button" onClick={() => onNavigate('architecture')}>Understand the trust boundary <ArrowRight size={14} /></button></div></section>
    <section className="docs-section"><SectionTitle index="05" title="Troubleshooting" subtitle="Fail-open behavior should keep work moving" /><div className="docs-faq"><details><summary>No live requests appear <ChevronRight size={14} /></summary><p>Confirm the proxy is running, restart the IDE after configuration, run editor-status, and clear repository/date filters.</p></details><details><summary>A request shows zero reduction <ChevronRight size={14} /></summary><p>Short or high-risk prompts may be intentionally unchanged. A verifier fallback records its reason and a labeled estimate; a non-empty request should never appear as an unexplained 0 → 0 measurement.</p></details><details><summary>LLMLingua-2 cannot load <ChevronRight size={14} /></summary><p>The learned adapter is default-on and warmed asynchronously in a persistent worker. Warmup, oversized input, or runtime failure uses verified query-aware extractive compression immediately.</p></details><details><summary>Token numbers differ from provider usage <ChevronRight size={14} /></summary><p>Local before/after values measure the serialized request. Actual provider input/output/cache usage is shown separately when exposed.</p></details></div></section>
  </div>
}

function ArchitectureGuide() {
  const [stageId, setStageId] = useState('shape')
  const stage = STAGES.find(item => item.id === stageId) || STAGES[0]
  const StageIcon = stage.icon
  return <div className="docs-document">
    <DocHeading eyebrow="Architecture & data flow" title="How TrimPy works end to end" icon={Network}>Explore the runtime topology, compiler decisions, trust boundaries, fallback paths, and observability model.</DocHeading>
    <section className="docs-section"><SectionTitle index="01" title="System topology" subtitle="Request plane and evidence plane remain separate" /><div className="architecture-map"><div className="architecture-clients"><span><UserRound size={18} /></span><b>AI clients</b><small>VS Code · JetBrains · CLI</small></div><ArrowRight className="architecture-arrow" size={20} /><div className="architecture-proxy"><span><Server size={18} /></span><b>Local proxy</b><small>Intercept · identify · forward</small></div><ArrowRight className="architecture-arrow" size={20} /><div className="architecture-compiler"><span><Workflow size={18} /></span><b>Context compiler</b><small>Protect · retrieve · compress · verify</small></div><ArrowRight className="architecture-arrow" size={20} /><div className="architecture-provider"><span><Sparkles size={18} /></span><b>Model provider</b><small>GitHub Copilot · upstream usage</small></div><div className="architecture-audit"><Database size={17} /><span><b>Local evidence plane</b><small>SQLite → validation → diff → manager proof</small></span></div></div></section>
    <section className="docs-section"><SectionTitle index="02" title="Interactive request pipeline" subtitle="Select a stage to inspect its contract" /><div className="architecture-stage-grid">{STAGES.map((item, index) => { const Icon = item.icon; return <button type="button" key={item.id} className={stageId === item.id ? 'active' : ''} onClick={() => setStageId(item.id)}><span>{index + 1}</span><Icon size={16} /><b>{item.title}</b><small>{item.layer}</small></button> })}</div><article className="architecture-stage-detail"><header><span><StageIcon size={21} /></span><div><small>{stage.layer} layer</small><h3>{stage.title}</h3></div></header><p>{stage.detail}</p><div><span><small>Input</small><b>{stage.input}</b></span><ArrowRight size={17} /><span><small>Output</small><b>{stage.output}</b></span></div><footer><ShieldCheck size={15} /><b>Invariant:</b> {stage.invariant}</footer></article></section>
    <section className="docs-section"><SectionTitle index="03" title="Trust boundaries" subtitle="Content can provide evidence without gaining instruction authority" /><div className="trust-table"><div className="head"><span>Boundary</span><span>Authority</span><span>Treatment</span></div>{[['System / developer', 'Trusted control', 'Protected from lossy compression'], ['Latest user directive', 'Task authority', 'Preserved verbatim; typed attachment may compress'], ['Historical conversation', 'Data only', 'Task-state summary without role escalation'], ['Tool / retrieved output', 'Untrusted data', 'Injection scan, authorization, query retrieval'], ['Calls / encrypted reasoning', 'Opaque protocol', 'Byte-equivalent preservation']].map(row => <div key={row[0]}><b>{row[0]}</b><mark>{row[1]}</mark><span>{row[2]}</span></div>)}</div></section>
    <section className="docs-section"><SectionTitle index="04" title="Failure behavior" subtitle="Reliability comes from explicit restoration paths" /><div className="failure-grid">{[['Compressor exception', 'Restore the original unit'], ['Missing critical anchor', 'Reinsert compactly, re-verify, then restore if needed'], ['Invalid JSON or code', 'Reject and record the failed check'], ['LLMLingua warming or unavailable', 'Use query-aware extractive fallback'], ['Worker latency exceeded', 'Forward unchanged with a labeled nonzero estimate'], ['Provider usage absent', 'Never claim billing truth']].map(([failure, behavior]) => <article key={failure}><CircleHelp size={16} /><b>{failure}</b><span>{behavior}</span></article>)}</div></section>
    <section className="docs-section"><SectionTitle index="05" title="Observability contract" subtitle="A manager should see sample size, value, trust, and provenance" /><div className="observability-strip"><article><Zap size={17} /><b>Value</b><span>Tokens removed, reduction, cache usage, estimated cost</span></article><article><ShieldCheck size={17} /><b>Trust</b><span>Retention, contracts, fallbacks, security, validation</span></article><article><GitBranch size={17} /><b>Provenance</b><span>Repository, IDE, model, tokenizer, request source</span></article><article><Database size={17} /><b>Evidence</b><span>Hashes, field paths, algorithms, verifier decisions</span></article></div></section>
  </div>
}

function ChangelogGuide() {
  return <div className="docs-document">
    <DocHeading eyebrow="Release changelog" title="Every notable change, versioned" icon={History}>The dashboard view mirrors CHANGELOG.md so release evidence is useful to operators and durable in the repository.</DocHeading>
    <div className="release-timeline">{RELEASES.map((release, index) => <article className={`release-card ${release.tone}`} key={release.version}><div className="release-marker"><span>{index + 1}</span></div><header><div><span>{release.date}</span><h3>{release.version}</h3><p>{release.summary}</p></div>{release.tone === 'current' ? <mark>Next release</mark> : <mark><CheckCircle2 size={12} /> Released</mark>}</header><div className="release-groups">{release.groups.map(([group, items]) => <section key={group}><b>{group}</b><ul>{items.map(item => <li key={item}>{item}</li>)}</ul></section>)}</div></article>)}</div>
    <section className="release-discipline"><Wrench size={18} /><div><h3>Release discipline</h3><p>Every user-visible feature, behavior change, security hardening, deprecation, and fix receives an Unreleased entry. A release moves those entries under a semantic version and date.</p></div><code>Added · Changed · Deprecated · Removed · Fixed · Security</code></section>
  </div>
}

function SectionTitle({ index, title, subtitle }) {
  return <div className="docs-section-title"><span>{index}</span><div><h3>{title}</h3><p>{subtitle}</p></div></div>
}

function CodeBlock({ children }) {
  return <pre className="docs-code"><span className="docs-code-dots"><i /><i /><i /></span><code>{children}</code></pre>
}
