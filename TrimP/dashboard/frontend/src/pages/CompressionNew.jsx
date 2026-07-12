import { useState } from 'react'
import { usePolling, useApi } from '../hooks/useApi.js'
import { Loading } from '../components/Charts.jsx'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { ChevronDown, ChevronRight } from 'lucide-react'

export default function Compression() {
  const { data: session } = useApi('/api/session/current')
  const sid = session?.id
  const { data: comps, loading } = usePolling(sid ? `/api/session/${sid}/compressions` : null, 5000)
  const { data: archives } = usePolling(sid ? `/api/session/${sid}/archives` : null, 10000)
  const [expandedCompressor, setExpandedCompressor] = useState(null)
  const [detailedEvents, setDetailedEvents] = useState({})

  if (loading && !comps) return <Loading />

  const chartData = (comps || []).map(c => ({
    name: c.compressor,
    saved: c.saved ?? 0,
    events: c.events ?? 0,
  }))

  // Load detailed events for a compressor
  const loadDetails = async (compressor) => {
    if (expandedCompressor === compressor) {
      setExpandedCompressor(null)
      return
    }
    
    setExpandedCompressor(compressor)
    
    if (!detailedEvents[compressor]) {
      try {
        const res = await fetch(`/api/session/${sid}/compressions/detailed?compressor=${compressor}`)
        const data = await res.json()
        setDetailedEvents(prev => ({ ...prev, [compressor]: data }))
      } catch (err) {
        console.error('Failed to load details:', err)
      }
    }
  }

  // Format timestamp to local time
  const formatTime = (isoString) => {
    if (!isoString) return '—'
    const date = new Date(isoString)
    return date.toLocaleTimeString() + ' ' + date.toLocaleDateString()
  }

  // Format relative time
  const formatRelative = (isoString) => {
    if (!isoString) return ''
    const date = new Date(isoString)
    const now = new Date()
    const diff = now - date
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)
    
    if (minutes < 1) return 'just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return `${days}d ago`
  }

  return (
    <div>
      {/* Session Info */}
      {session && (
        <div className="card" style={{ marginBottom: '1.5rem', background: 'linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)', color: 'white' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem' }}>
                📁 {session.repository || 'Unknown'} 
                <span style={{ opacity: 0.8, fontSize: '0.9rem', marginLeft: '0.5rem' }}>
                  ({session.branch || 'no branch'})
                </span>
              </h3>
              <div style={{ fontSize: '0.85rem', opacity: 0.9, marginTop: '0.25rem' }}>
                Started: {formatTime(session.started_at)} ({formatRelative(session.started_at)})
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '2rem', fontWeight: '600' }}>
                {session.tokens_saved?.toLocaleString() || 0}
              </div>
              <div style={{ fontSize: '0.85rem', opacity: 0.9 }}>tokens saved</div>
            </div>
          </div>
        </div>
      )}

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

      {/* Table with expandable rows */}
      <div className="card">
        <h2>Compression Breakdown (Click to expand)</h2>
        <table>
          <thead>
            <tr>
              <th style={{ width: '30px' }}></th>
              <th>Compressor</th>
              <th>Events</th>
              <th>Before (tokens)</th>
              <th>After (tokens)</th>
              <th>Saved</th>
              <th>Ratio</th>
            </tr>
          </thead>
          <tbody>
            {(comps || []).map(c => {
              const ratio = c.tokens_before > 0 ? (c.saved / c.tokens_before * 100).toFixed(0) : 0
              const isExpanded = expandedCompressor === c.compressor
              const details = detailedEvents[c.compressor]
              
              return (
                <>
                  <tr 
                    key={c.compressor}
                    onClick={() => loadDetails(c.compressor)}
                    style={{ cursor: 'pointer', background: isExpanded ? 'var(--bg)' : 'transparent' }}
                  >
                    <td>
                      {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </td>
                    <td style={{ color: 'var(--accent)', fontWeight: isExpanded ? '600' : '400' }}>
                      {c.compressor}
                    </td>
                    <td>{c.events?.toLocaleString()}</td>
                    <td>{c.tokens_before?.toLocaleString()}</td>
                    <td>{c.tokens_after?.toLocaleString()}</td>
                    <td style={{ color: 'var(--green)', fontWeight: '600' }}>
                      {c.saved?.toLocaleString()}
                    </td>
                    <td>{ratio}%</td>
                  </tr>
                  
                  {isExpanded && details && (
                    <tr>
                      <td colSpan="7" style={{ padding: 0, background: 'var(--bg)' }}>
                        <div style={{ padding: '1rem', borderTop: '1px solid var(--border)' }}>
                          <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: 'var(--muted)' }}>
                            Individual Compressions ({details.length} events)
                          </h4>
                          <table style={{ width: '100%', fontSize: '0.85rem' }}>
                            <thead>
                              <tr>
                                <th>Time</th>
                                <th>Before</th>
                                <th>After</th>
                                <th>Saved</th>
                                <th>%</th>
                              </tr>
                            </thead>
                            <tbody>
                              {details.map((event, idx) => {
                                const eventRatio = event.tokens_before > 0 
                                  ? ((event.tokens_before - event.tokens_after) / event.tokens_before * 100).toFixed(1)
                                  : 0
                                return (
                                  <tr key={idx}>
                                    <td style={{ color: 'var(--muted)' }}>
                                      {formatTime(event.compressed_at)}
                                      <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>
                                        {formatRelative(event.compressed_at)}
                                      </div>
                                    </td>
                                    <td>{event.tokens_before?.toLocaleString()}</td>
                                    <td>{event.tokens_after?.toLocaleString()}</td>
                                    <td style={{ color: 'var(--green)' }}>
                                      {(event.tokens_before - event.tokens_after).toLocaleString()}
                                    </td>
                                    <td>{eventRatio}%</td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      </td>
                    </tr>
                  )}
                  
                  {isExpanded && !details && (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center', padding: '1rem', color: 'var(--muted)' }}>
                        Loading details...
                      </td>
                    </tr>
                  )}
                </>
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
                  <td style={{ color: 'var(--muted)' }}>
                    {formatTime(a.archived_at)}
                    <div style={{ fontSize: '0.75rem' }}>{formatRelative(a.archived_at)}</div>
                  </td>
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
