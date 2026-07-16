import React, { useState, useEffect, useRef } from 'react'
import { Activity, TrendingUp, Zap, Database, Clock, RefreshCw } from 'lucide-react'
import { useRefreshTick } from '../hooks/useApi.js'

const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4']

function fmtTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('en-US', {
    hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function fmtRelative(iso) {
  if (!iso) return ''
  const s = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (s < 5)    return 'just now'
  if (s < 60)   return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

function StatCard({ icon: Icon, label, value, color, sub }) {
  return (
    <div className="card" style={{ padding: '1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div style={{
          width: 44, height: 44, borderRadius: 10,
          background: color + '22',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={22} style={{ color }} />
        </div>
        <div>
          <div style={{ fontSize: '0.78rem', opacity: 0.6, marginBottom: '0.15rem' }}>{label}</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
          {sub && <div style={{ fontSize: '0.72rem', opacity: 0.5, marginTop: '0.2rem' }}>{sub}</div>}
        </div>
      </div>
    </div>
  )
}

export default function CompressionLive() {
  const [recentComps,  setRecentComps]  = useState([])
  const [summaryComps, setSummaryComps] = useState([])
  const [session,      setSession]      = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [lastUpdate,   setLastUpdate]   = useState(null)
  const [liveLimit,    setLiveLimit]    = useState(20)
  const [paused,       setPaused]       = useState(false)
  const [wsStatus,     setWsStatus]     = useState('connecting')
  const wsRef    = useRef(null)
  const pauseRef = useRef(false)
  const mountedRef = useRef(true)
  const refreshTick = useRefreshTick()

  // Keep pauseRef in sync so the ws callback sees the latest value
  useEffect(() => { pauseRef.current = paused }, [paused])

  // WebSocket for instant push — reconnects on disconnect
  useEffect(() => {
    mountedRef.current = true
    connectWs()
    return () => {
      mountedRef.current = false
      wsRef.current?.close()
    }
  }, [])

  function connectWs() {
    try {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/live`)
      ws.onopen    = () => setWsStatus('connected')
      ws.onclose   = () => {
        setWsStatus('disconnected')
        if (mountedRef.current) setTimeout(connectWs, 3000)
      }
      ws.onerror   = () => setWsStatus('error')
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          // Any server push triggers an immediate data refresh
          if ((msg.type === 'compression' || msg.type === 'stats') && !pauseRef.current) {
            fetchData()
          }
        } catch {}
      }
      wsRef.current = ws
    } catch { setWsStatus('error') }
  }

  async function fetchData() {
    if (pauseRef.current) return
    try {
      const [sessRes, recentRes] = await Promise.all([
        fetch('/api/session/current'),
        fetch(`/api/compressions/recent?range=all&limit=${liveLimit}`),
      ])

      let sessData = null
      if (sessRes.ok) {
        sessData = await sessRes.json()
        setSession(sessData)
      }

      if (recentRes.ok) {
        const data = await recentRes.json()
        setRecentComps(data)
      }

      // Per-session summary
      if (sessData?.id) {
        const sumRes = await fetch(`/api/session/${sessData.id}/compressions`)
        if (sumRes.ok) setSummaryComps(await sumRes.json())
      }

      setLastUpdate(new Date())
    } catch (e) {
      console.error('Fetch error:', e)
    } finally {
      setLoading(false)
    }
  }

  // The shared one-second refresh signal is the polling fallback; WebSocket
  // pushes still refresh immediately when the server emits an event.
  useEffect(() => { fetchData() }, [liveLimit, refreshTick])

  const totalSaved  = recentComps.reduce((s, c) => s + (c.tokens_saved ?? 0), 0)
  const totalBefore = recentComps.reduce((s, c) => s + (c.tokens_before ?? 0), 0)
  const avgPct      = totalBefore > 0 ? ((totalSaved / totalBefore) * 100).toFixed(1) : '0'

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.8rem' }}>
            <Activity size={30} style={{ color: '#3b82f6' }} />
            Live Compression Monitor
          </h1>
          <p style={{ margin: '0.35rem 0 0', opacity: 0.6, fontSize: '0.875rem' }}>
            Tracks every compression across configured IDE and Copilot chat sessions • Refreshes every second
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* WS badge */}
          <span style={{
            padding: '0.3rem 0.7rem', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 700,
            background: wsStatus === 'connected' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
            color:      wsStatus === 'connected' ? '#10b981'               : '#ef4444',
            border: `1px solid ${wsStatus === 'connected' ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`,
          }}>
            {wsStatus === 'connected' ? '● LIVE' : '○ ' + wsStatus.toUpperCase()}
          </span>

          {/* Limit selector */}
          <select
            value={liveLimit}
            onChange={e => setLiveLimit(Number(e.target.value))}
            style={{
              padding: '0.35rem 0.5rem', borderRadius: '6px',
              border: '1px solid var(--border)',
              background: 'var(--card-bg)', color: 'var(--fg)', fontSize: '0.83rem',
            }}
          >
            {[5, 10, 15, 20, 25, 30].map(n => (
              <option key={n} value={n}>Last {n}</option>
            ))}
          </select>

          <button
            onClick={() => setPaused(p => !p)}
            aria-label={paused ? 'Resume live activity' : 'Pause live activity'}
            style={{
              padding: '0.35rem 0.9rem', borderRadius: '6px', border: 'none',
              cursor: 'pointer', fontWeight: 700, fontSize: '0.83rem',
              background: paused ? '#10b981' : '#6b7280', color: 'white',
            }}
          >
            {paused ? '▶ Resume' : '⏸ Pause'}
          </button>

          <button
            onClick={fetchData}
            title="Refresh now"
            aria-label="Refresh live activity"
            style={{
              padding: '0.35rem 0.6rem', borderRadius: '6px',
              border: '1px solid var(--border)', cursor: 'pointer',
              background: 'transparent', color: 'var(--fg)',
            }}
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {/* ── Current Session Info ── */}
      {session && (
        <div className="card" style={{
          marginBottom: '1.5rem', padding: '1.25rem',
          background: 'linear-gradient(135deg, #3b82f6 0%, #7c3aed 100%)', color: 'white',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem' }}>
            {[
              {
                label: 'Session Started',
                main: fmtTime(session.started_at),
                sub: new Date(session.started_at).toLocaleDateString(),
              },
              {
                label: 'Model',
                main: session.model || 'Copilot Enterprise',
                sub: `Status: ${session.status}`,
              },
              {
                label: 'Tokens Saved (session)',
                main: (session.tokens_saved || 0).toLocaleString(),
                sub: `≈ $${((session.tokens_saved || 0) * 0.000003).toFixed(3)} saved`,
              },
              {
                label: 'Chat Turns',
                main: session.total_tokens_in > 0 ? '✓ Tracking' : '⏳ Waiting',
                sub: `In: ${(session.total_tokens_in||0).toLocaleString()} / Out: ${(session.total_tokens_out||0).toLocaleString()}`,
              },
            ].map(({ label, main, sub }) => (
              <div key={label}>
                <div style={{ fontSize: '0.72rem', opacity: 0.8, marginBottom: '0.2rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
                <div style={{ fontWeight: 700, fontSize: '1.05rem' }}>{main}</div>
                <div style={{ fontSize: '0.75rem', opacity: 0.7 }}>{sub}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Summary stats ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <StatCard icon={TrendingUp} label="Tokens Saved"  value={totalSaved.toLocaleString()}         color="#3b82f6" sub={`from last ${liveLimit} events`} />
        <StatCard icon={Zap}        label="Avg Savings"   value={`${avgPct}%`}                         color="#8b5cf6" sub="per compression" />
        <StatCard icon={Database}   label="Events Shown"  value={recentComps.length.toString()}        color="#ec4899" sub="in current view" />
        <StatCard icon={Clock}      label="Last Update"   value={lastUpdate ? fmtTime(lastUpdate.toISOString()) : '—'} color="#f59e0b" sub="auto-refreshing" />
      </div>

      {/* ── 🕐 RECENT COMPRESSIONS table ── */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            🕐 RECENT COMPRESSIONS
            <span style={{ fontSize: '0.78rem', fontWeight: 400, opacity: 0.55 }}>(Last {liveLimit})</span>
          </h3>
          <span style={{ fontSize: '0.72rem', opacity: 0.45 }}>
            {lastUpdate ? `Updated ${fmtRelative(lastUpdate.toISOString())}` : 'Loading...'}
          </span>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem', opacity: 0.5 }}>
            <p>Loading compression data…</p>
          </div>
        ) : recentComps.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', opacity: 0.55, lineHeight: 1.7 }}>
            <Activity size={44} style={{ marginBottom: '0.75rem' }} />
            <p style={{ fontWeight: 600, fontSize: '1rem', margin: '0 0 0.5rem' }}>No compressions recorded yet.</p>
            <p style={{ fontSize: '0.85rem', margin: 0 }}>
              Start the proxy: <code>TrimP proxy start --upstream github-copilot</code><br />
              Set env: <code>export OPENAI_BASE_URL=http://localhost:8765</code><br />
              Then send a message from PyCharm — it will appear here instantly.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem', fontFamily: 'monospace' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  {['time', 'algorithm', 'tokens', 'saved', 'session'].map(h => (
                    <th key={h} style={{
                      padding: '0.6rem 1rem',
                      textAlign: h === 'tokens' || h === 'saved' ? 'right' : 'left',
                      opacity: 0.65, fontWeight: 700, letterSpacing: '0.04em',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentComps.map((c, i) => {
                  const saved = c.tokens_saved ?? (c.tokens_before - c.tokens_after)
                  const pct   = c.tokens_before > 0
                    ? ((saved / c.tokens_before) * 100).toFixed(1)
                    : '0'
                  const isNew = i === 0
                  return (
                    <tr key={c.id ?? i} style={{
                      borderBottom: '1px solid var(--border)',
                      background: isNew ? 'rgba(59,130,246,0.07)' : 'transparent',
                      transition: 'background 0.4s',
                    }}>
                      <td style={{ padding: '0.6rem 1rem', whiteSpace: 'nowrap', opacity: 0.7 }}>
                        {fmtTime(c.compressed_at)}
                        {isNew && (
                          <span style={{
                            marginLeft: '0.5rem', fontSize: '0.68rem',
                            background: '#3b82f6', color: 'white',
                            padding: '0.1rem 0.4rem', borderRadius: '4px',
                          }}>NEW</span>
                        )}
                      </td>
                      <td style={{ padding: '0.6rem 1rem' }}>
                        <span style={{
                          padding: '0.2rem 0.65rem', borderRadius: '10px', fontWeight: 600,
                          fontSize: '0.8rem',
                          background: COLORS[i % COLORS.length] + '22',
                          color: COLORS[i % COLORS.length],
                        }}>
                          {c.compressor}
                        </span>
                      </td>
                      <td style={{ padding: '0.6rem 1rem', textAlign: 'right', fontWeight: 600 }}>
                        {c.tokens_before}→{c.tokens_after}
                      </td>
                      <td style={{ padding: '0.6rem 1rem', textAlign: 'right' }}>
                        <span style={{ color: '#10b981', fontWeight: 700 }}>{pct}%</span>
                        <span style={{ opacity: 0.45, marginLeft: '0.4rem', fontSize: '0.78rem' }}>({saved})</span>
                      </td>
                      <td style={{ padding: '0.6rem 1rem', opacity: 0.4, fontSize: '0.78rem' }}>
                        {c.session_id ? c.session_id.slice(0, 8) + '…' : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Summary by Compressor (current session) ── */}
      {summaryComps.length > 0 && (
        <div className="card">
          <h3 style={{ margin: '0 0 1rem 0' }}>Session Summary by Algorithm</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                {['Algorithm', 'Events', 'Before', 'After', 'Saved', 'Avg / event'].map((h, j) => (
                  <th key={h} style={{
                    padding: '0.5rem 0.75rem',
                    textAlign: j === 0 ? 'left' : 'right',
                    opacity: 0.65, fontWeight: 700,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {summaryComps.map((c, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.6rem 0.75rem', fontWeight: 600, color: COLORS[i % COLORS.length] }}>
                    {c.compressor}
                  </td>
                  <td style={{ padding: '0.6rem 0.75rem', textAlign: 'right' }}>{c.events}</td>
                  <td style={{ padding: '0.6rem 0.75rem', textAlign: 'right', opacity: 0.6 }}>{(c.tokens_before || 0).toLocaleString()}</td>
                  <td style={{ padding: '0.6rem 0.75rem', textAlign: 'right', opacity: 0.6 }}>{(c.tokens_after || 0).toLocaleString()}</td>
                  <td style={{ padding: '0.6rem 0.75rem', textAlign: 'right', color: '#10b981', fontWeight: 700 }}>{(c.saved || 0).toLocaleString()}</td>
                  <td style={{ padding: '0.6rem 0.75rem', textAlign: 'right', opacity: 0.6 }}>
                    {c.events > 0 ? Math.round((c.saved || 0) / c.events) : 0} tkns
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
