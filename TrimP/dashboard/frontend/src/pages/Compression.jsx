import { usePolling, useApi } from '../hooks/useApi.js'
import { Loading } from '../components/Charts.jsx'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'

export default function Compression() {
  const { data: session } = useApi('/api/session/current')
  const sid = session?.id
  const { data: comps, loading } = usePolling(sid ? `/api/session/${sid}/compressions` : null, 5000)
  const { data: archives } = usePolling(sid ? `/api/session/${sid}/archives` : null, 10000)

  if (loading && !comps) return <Loading />

  const chartData = (comps || []).map(c => ({
    name: c.compressor,
    saved: c.saved ?? 0,
    events: c.events ?? 0,
  }))

  return (
    <div>
      {/* Bar chart */}
      {chartData.length > 0 && (
        <div className="card">
          <h2>Tokens Saved by Compressor</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" stroke="var(--muted)" fontSize={11} />
              <YAxis stroke="var(--muted)" fontSize={11} />
              <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)' }} />
              <Bar dataKey="saved" name="Tokens Saved" radius={[4,4,0,0]}>
                {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table */}
      <div className="card">
        <h2>Compression Breakdown</h2>
        <table>
          <thead>
            <tr><th>Compressor</th><th>Events</th><th>Before (tokens)</th><th>After (tokens)</th><th>Saved</th><th>Ratio</th></tr>
          </thead>
          <tbody>
            {(comps || []).map(c => {
              const ratio = c.tokens_before > 0 ? (c.saved / c.tokens_before * 100).toFixed(0) : 0
              return (
                <tr key={c.compressor}>
                  <td style={{ color: 'var(--accent)' }}>{c.compressor}</td>
                  <td>{c.events?.toLocaleString()}</td>
                  <td>{c.tokens_before?.toLocaleString()}</td>
                  <td>{c.tokens_after?.toLocaleString()}</td>
                  <td style={{ color: 'var(--green)' }}>{c.saved?.toLocaleString()}</td>
                  <td>{ratio}%</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Archives */}
      {archives && archives.length > 0 && (
        <div className="card">
          <h2>Progressive Disclosure Archives ({archives.length})</h2>
          <table>
            <thead><tr><th>Key</th><th>Tool</th><th>Size (chars)</th><th>Archived</th><th>Summary</th></tr></thead>
            <tbody>
              {archives.map(a => (
                <tr key={a.archive_key}>
                  <td style={{ fontFamily: 'monospace', color: 'var(--purple)' }}>{a.archive_key}</td>
                  <td>{a.tool_name ?? '—'}</td>
                  <td>{a.char_count?.toLocaleString()}</td>
                  <td style={{ color: 'var(--muted)' }}>{a.archived_at?.slice(0, 16)}</td>
                  <td style={{ color: 'var(--muted)', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const COLORS = ['#58a6ff','#3fb950','#d29922','#bc8cff','#f85149','#e3b341','#39c5cf','#ff7b72','#a5d6ff']
