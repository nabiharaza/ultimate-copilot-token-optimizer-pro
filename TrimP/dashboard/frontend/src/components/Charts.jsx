export function GradeCircle({ grade, score }) {
  const colors = { S: '#3fb950', A: '#58a6ff', B: '#d29922', C: '#e3b341', D: '#f85149', F: '#b22222' }
  const color = colors[grade] || '#8b949e'
  const pct = Math.round((score || 0) * 100)
  const r = 36; const circ = 2 * Math.PI * r
  const dash = circ * (score || 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem' }}>
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="var(--border)" strokeWidth="8" />
        <circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
          transform="rotate(-90 48 48)" style={{ transition: 'stroke-dasharray 0.5s' }} />
        <text x="48" y="52" textAnchor="middle" fill={color} fontSize="22" fontWeight="bold">{grade}</text>
      </svg>
      <span style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>{pct}%</span>
    </div>
  )
}

export function ScoreBar({ score, color }) {
  const pct = Math.round((score || 0) * 100)
  const barColor = color || (score >= 0.8 ? '#3fb950' : score >= 0.5 ? '#d29922' : '#f85149')
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <div className="bar-outer" style={{ flex: 1 }}>
        <div className="bar-inner" style={{ width: `${pct}%`, background: barColor }} />
      </div>
      <span style={{ minWidth: '3rem', color: 'var(--muted)', fontSize: '0.8rem' }}>{pct}%</span>
    </div>
  )
}

export function MetricCard({ label, value, color, sub }) {
  return (
    <div className="metric-card">
      <div className="metric-value" style={color ? { color } : {}}>{value ?? '—'}</div>
      <div className="metric-label">{label}</div>
      {sub && <div style={{ color: 'var(--muted)', fontSize: '0.75rem', marginTop: '0.25rem' }}>{sub}</div>}
    </div>
  )
}

export function Loading() {
  return <div style={{ color: 'var(--muted)', padding: '2rem', textAlign: 'center' }}>Loading…</div>
}

export function ErrorMsg({ msg }) {
  return <div style={{ color: 'var(--red)', padding: '1rem' }}>⚠ {msg}</div>
}
