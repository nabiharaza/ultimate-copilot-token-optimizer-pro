import { useApi, usePolling } from '../hooks/useApi.js'
import { GradeCircle, ScoreBar, Loading } from '../components/Charts.jsx'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts'

export default function Quality() {
  const { data: session } = useApi('/api/session/current')
  const sid = session?.id
  const { data: quality, loading } = usePolling(sid ? `/api/session/${sid}/quality` : null, 5000)
  const { data: loops } = usePolling(sid ? `/api/session/${sid}/loops` : null, 10000)

  if (loading && !quality) return <Loading />
  if (!quality) return <div style={{ color: 'var(--muted)', padding: '2rem' }}>No quality data yet.</div>

  const signals = [
    { name: 'Conciseness', key: 'conciseness', help: 'Are prompts and replies compact without losing intent?' },
    { name: 'Compression', key: 'compression', help: 'How much safe reduction was achieved?' },
    { name: 'Context fit', key: 'context_utilization', help: 'How efficiently is the model context window being used?' },
    { name: 'Model routing', key: 'model_routing', help: 'Was the selected model appropriate for the task?' },
    { name: 'Loop-free', key: 'loop_rate', help: 'Did the session avoid repeated tool or action loops?' },
    { name: 'Cache health', key: 'cache_hit_rate', help: 'How much reusable context stayed cache-aligned?' },
  ]

  const radarData = signals.map(s => ({ subject: s.name, score: Math.round((quality[s.key] ?? 0) * 100) }))

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
          <GradeCircle grade={quality.grade} score={quality.overall} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>Session</div>
            <div style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{sid?.slice(0, 16)}…</div>
          </div>
        </div>

        <div className="card">
          <h2>Operational quality signals</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {signals.map(s => (
              <div key={s.key}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                  <span title={s.help} style={{ color: 'var(--muted)', fontSize: '0.85rem', cursor: 'help' }}>{s.name}</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>{Math.round((quality[s.key] ?? 0) * 100)}%</span>
                </div>
                <ScoreBar score={quality[s.key] ?? 0} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Radar chart */}
      <div className="card">
        <h2>Quality Radar</h2>
        <ResponsiveContainer width="100%" height={280}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="var(--border)" />
            <PolarAngleAxis dataKey="subject" stroke="var(--muted)" fontSize={12} />
            <Radar name="Score" dataKey="score" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.2} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Loops */}
      {loops && loops.length > 0 && (
        <div className="card">
          <h2>⚠ Loop Detections ({loops.length})</h2>
          <table>
            <thead><tr><th>Type</th><th>Pattern</th><th>Repeats</th><th>Detected</th></tr></thead>
            <tbody>
              {loops.map(l => (
                <tr key={l.id}>
                  <td style={{ color: 'var(--red)' }}>{l.loop_type}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{l.pattern}</td>
                  <td>{l.repeat_count}</td>
                  <td style={{ color: 'var(--muted)' }}>{l.detected_at?.slice(0, 16)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
