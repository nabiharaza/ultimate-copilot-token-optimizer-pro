import { useState, useEffect } from 'react'
import { usePolling } from '../hooks/useApi.js'
import { Loading } from '../components/Charts.jsx'

export default function SessionDetail({ sessionId, onBack }) {
  const { data: session, loading } = usePolling(`/api/session/${sessionId}`, 5000)
  const [selectedTurn, setSelectedTurn] = useState(null)

  if (loading && !session) return <Loading />
  if (!session || session.error) {
    return (
      <div className="card">
        <button onClick={onBack} style={{ marginBottom: '1rem' }}>← Back to Sessions</button>
        <p style={{ color: 'var(--red)' }}>Session not found or error loading</p>
      </div>
    )
  }

  const turns = session.turns || []

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <button onClick={onBack} style={{ marginBottom: '1rem', padding: '0.5rem 1rem', cursor: 'pointer' }}>
          ← Back to Sessions
        </button>
        <h1 style={{ margin: '0 0 1rem 0', fontSize: '1.8rem' }}>Session Details</h1>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', fontSize: '0.9rem' }}>
          <div>
            <div style={{ color: 'var(--muted)', marginBottom: '0.25rem' }}>Session ID</div>
            <div style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{session.id?.slice(0, 20)}...</div>
          </div>
          <div>
            <div style={{ color: 'var(--muted)', marginBottom: '0.25rem' }}>Repository</div>
            <div style={{ fontWeight: 'bold' }}>{session.repository || '—'}</div>
          </div>
          <div>
            <div style={{ color: 'var(--muted)', marginBottom: '0.25rem' }}>Branch</div>
            <div>{session.branch || '—'}</div>
          </div>
          <div>
            <div style={{ color: 'var(--muted)', marginBottom: '0.25rem' }}>Started</div>
            <div>{new Date(session.started_at).toLocaleString()}</div>
          </div>
          <div>
            <div style={{ color: 'var(--muted)', marginBottom: '0.25rem' }}>Tokens In</div>
            <div style={{ color: 'var(--cyan)', fontWeight: 'bold' }}>{(session.total_tokens_in || 0).toLocaleString()}</div>
          </div>
          <div>
            <div style={{ color: 'var(--muted)', marginBottom: '0.25rem' }}>Tokens Out</div>
            <div style={{ color: 'var(--green)', fontWeight: 'bold' }}>{(session.total_tokens_out || 0).toLocaleString()}</div>
          </div>
          <div>
            <div style={{ color: 'var(--muted)', marginBottom: '0.25rem' }}>Model</div>
            <div>{session.model || 'claude-sonnet-4.5'}</div>
          </div>
          <div>
            <div style={{ color: 'var(--muted)', marginBottom: '0.25rem' }}>Status</div>
            <div style={{ 
              color: session.status === 'active' ? 'var(--green)' : 'var(--muted)',
              fontWeight: 'bold'
            }}>{session.status || 'active'}</div>
          </div>
        </div>
      </div>

      {/* Conversation Turns */}
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Conversation ({turns.length} turns)</h2>
        
        {turns.length === 0 ? (
          <p style={{ color: 'var(--muted)', textAlign: 'center', padding: '2rem' }}>
            No conversation turns recorded yet.
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {turns.map((turn, idx) => (
              <div 
                key={idx} 
                style={{ 
                  border: '1px solid var(--border)', 
                  borderRadius: '8px', 
                  overflow: 'hidden',
                  background: selectedTurn === idx ? 'rgba(0, 150, 255, 0.05)' : 'transparent'
                }}
              >
                {/* Turn Header */}
                <div 
                  style={{ 
                    background: 'var(--card-bg)', 
                    padding: '0.75rem 1rem', 
                    borderBottom: '1px solid var(--border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    cursor: 'pointer'
                  }}
                  onClick={() => setSelectedTurn(selectedTurn === idx ? null : idx)}
                >
                  <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <span style={{ 
                      background: 'var(--cyan)', 
                      color: 'black', 
                      padding: '0.25rem 0.75rem', 
                      borderRadius: '4px',
                      fontWeight: 'bold',
                      fontSize: '0.85rem'
                    }}>
                      Turn {turn.turn_index}
                    </span>
                    <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
                      {new Date(turn.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.85rem' }}>
                    <span>
                      <span style={{ color: 'var(--muted)' }}>In:</span> 
                      <span style={{ color: 'var(--cyan)', fontWeight: 'bold', marginLeft: '0.5rem' }}>
                        {turn.tokens_in || 0}
                      </span>
                    </span>
                    <span>
                      <span style={{ color: 'var(--muted)' }}>Out:</span>
                      <span style={{ color: 'var(--green)', fontWeight: 'bold', marginLeft: '0.5rem' }}>
                        {turn.tokens_out || 0}
                      </span>
                    </span>
                    <span style={{ color: 'var(--muted)' }}>
                      {selectedTurn === idx ? '▼' : '▶'}
                    </span>
                  </div>
                </div>

                {/* Turn Content (expandable) */}
                {selectedTurn === idx && (
                  <div style={{ padding: '1.5rem' }}>
                    {/* User Message */}
                    <div style={{ marginBottom: '1.5rem' }}>
                      <div style={{ 
                        color: 'var(--cyan)', 
                        fontWeight: 'bold', 
                        marginBottom: '0.5rem',
                        fontSize: '0.9rem'
                      }}>
                        👤 User
                      </div>
                      <div style={{ 
                        background: 'rgba(0, 150, 255, 0.1)', 
                        padding: '1rem', 
                        borderRadius: '6px',
                        borderLeft: '3px solid var(--cyan)',
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'system-ui, sans-serif',
                        lineHeight: '1.6',
                        color: 'var(--text)'
                      }}>
                        {turn.user_message || '(no message)'}
                      </div>
                    </div>

                    {/* Assistant Response */}
                    <div>
                      <div style={{ 
                        color: 'var(--green)', 
                        fontWeight: 'bold', 
                        marginBottom: '0.5rem',
                        fontSize: '0.9rem'
                      }}>
                        🤖 Assistant
                      </div>
                      <div style={{ 
                        background: 'rgba(0, 255, 100, 0.05)', 
                        padding: '1rem', 
                        borderRadius: '6px',
                        borderLeft: '3px solid var(--green)',
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'system-ui, sans-serif',
                        lineHeight: '1.6',
                        color: 'var(--text)',
                        maxHeight: '400px',
                        overflowY: 'auto'
                      }}>
                        {turn.assistant_response || '(no response)'}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Compressions Section */}
      {session.compressions && session.compressions.length > 0 && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <h2 style={{ marginTop: 0 }}>Compressions ({session.compressions.length})</h2>
          <table style={{ width: '100%', fontSize: '0.9rem' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Compressor</th>
                <th style={{ textAlign: 'right' }}>Before</th>
                <th style={{ textAlign: 'right' }}>After</th>
                <th style={{ textAlign: 'right' }}>Saved</th>
                <th style={{ textAlign: 'right' }}>%</th>
                <th style={{ textAlign: 'left' }}>Time</th>
              </tr>
            </thead>
            <tbody>
              {session.compressions.slice(0, 20).map((c, idx) => {
                const saved = c.tokens_before - c.tokens_after
                const pct = c.tokens_before > 0 ? ((saved / c.tokens_before) * 100).toFixed(1) : 0
                return (
                  <tr key={idx}>
                    <td><span style={{ 
                      background: 'var(--cyan)', 
                      color: 'black', 
                      padding: '0.2rem 0.5rem', 
                      borderRadius: '4px',
                      fontSize: '0.8rem',
                      fontWeight: 'bold'
                    }}>{c.compressor}</span></td>
                    <td style={{ textAlign: 'right', color: 'var(--muted)' }}>{c.tokens_before}</td>
                    <td style={{ textAlign: 'right', color: 'var(--cyan)' }}>{c.tokens_after}</td>
                    <td style={{ textAlign: 'right', color: 'var(--green)', fontWeight: 'bold' }}>{saved}</td>
                    <td style={{ textAlign: 'right', color: 'var(--green)' }}>{pct}%</td>
                    <td style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>
                      {new Date(c.compressed_at).toLocaleTimeString()}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
