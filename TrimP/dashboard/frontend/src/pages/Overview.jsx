import { usePolling } from '../hooks/useApi.js'
import { GradeCircle, MetricCard, ScoreBar, Loading, ErrorMsg } from '../components/Charts.jsx'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid } from 'recharts'

export default function Overview() {
  const { data: session } = usePolling('/api/session/current', 5000)
  const { data: savings } = usePolling('/api/savings', 10000)
  const { data: trends } = usePolling('/api/trends/daily?days=14', 30000)
  const sid = session?.id

  const { data: quality, loading, error } = usePolling(
    sid ? `/api/session/${sid}/quality` : null, 5000
  )

  if (!session) return <Loading />

  const saved = session?.tokens_saved ?? 0
  const grade = quality?.grade ?? session?.quality_grade ?? '?'
  const score = quality?.overall ?? 0

  return (
    <div>
      {/* Top metrics */}
      <div className="metric-grid">
        <MetricCard label="Quality Grade" value={grade} color={gradeColor(grade)} />
        <MetricCard label="Tokens Saved" value={saved?.toLocaleString()} color="var(--green)" />
        <MetricCard label="$ Saved (Sonnet)" value={`$${savings?.savings?.sonnet?.toFixed(4) ?? '0.0000'}`} color="var(--accent)" />
        <MetricCard label="Tokens In" value={session?.total_tokens_in?.toLocaleString()} />
        <MetricCard label="Tokens Out" value={session?.total_tokens_out?.toLocaleString()} />
        <MetricCard label="Model" value={session?.model ?? '?'} color="var(--purple)" sub={session?.branch} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        {/* Grade circle */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <GradeCircle grade={grade} score={score} />
          <h3 style={{ marginTop: '0.75rem' }}>Overall Score</h3>
        </div>

        {/* Quality signals */}
        <div className="card">
          <h2>Quality Signals</h2>
          {quality && (
            <table style={{ width: '100%' }}>
              <tbody>
                {[
                  ['Conciseness', quality.conciseness],
                  ['Compression', quality.compression],
                  ['Context Utilization', quality.context_utilization],
                  ['Model Routing', quality.model_routing],
                  ['Loop-free Rate', quality.loop_rate],
                  ['Cache Hit Rate', quality.cache_hit_rate],
                ].map(([name, val]) => (
                  <tr key={name}>
                    <td style={{ width: '180px', color: 'var(--muted)' }}>{name}</td>
                    <td><ScoreBar score={val} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {loading && <Loading />}
          {error && <ErrorMsg msg={error} />}
        </div>
      </div>

      {/* Trend chart */}
      {trends && trends.length > 0 && (
        <div className="card">
          <h2>14-Day Token Savings Trend</h2>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="day" stroke="var(--muted)" fontSize={11} />
              <YAxis stroke="var(--muted)" fontSize={11} />
              <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)' }} />
              <Area type="monotone" dataKey="saved" stroke="var(--green)" fill="rgba(63,185,80,0.15)" name="Tokens Saved" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Session info */}
      <div className="card">
        <h2>Current Session</h2>
        <table>
          <tbody>
            {[
              ['ID', session?.id],
              ['Repository', session?.repository],
              ['Branch', session?.branch],
              ['CWD', session?.cwd],
              ['Started', session?.started_at?.slice(0, 19)],
              ['Status', session?.status],
            ].map(([k, v]) => (
              <tr key={k}><td style={{ color: 'var(--muted)', width: '120px' }}>{k}</td><td>{v ?? '—'}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function gradeColor(g) {
  return { S: '#3fb950', A: '#58a6ff', B: '#d29922', C: '#e3b341', D: '#f85149', F: '#b22222' }[g] || 'var(--muted)'
}
