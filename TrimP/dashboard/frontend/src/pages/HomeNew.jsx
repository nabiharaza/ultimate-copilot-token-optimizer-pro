import { usePolling } from '../hooks/useApi.js'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Activity, DollarSign, Zap, TrendingUp } from 'lucide-react'

export default function Home() {
  const { data: session } = usePolling('/api/session/current', 3000)
  const { data: savings } = usePolling('/api/savings', 10000)
  const { data: trends }  = usePolling('/api/trends/daily?days=30', 30000)
  const { data: config }  = usePolling('/api/config', 15000)
  const { data: recentComps } = usePolling('/api/compressions/recent?range=all&limit=10', 2000)

  const sessionSavings = session?.tokens_saved ?? 0
  const allTimeSavings = savings?.tokens_saved ?? 0

  const totalTokens = (session?.total_tokens_in ?? 0) + (session?.total_tokens_out ?? 0)
  const savingsPercent = totalTokens > 0 ? Math.round((sessionSavings / totalTokens) * 100) : 0

  const isEnabled = (key) => config?.[`compression.${key}.enabled`] !== 'false'

  return (
    <div className="home-page">
      {/* Status Banner */}
      <div className="status-banner">
        <Activity size={20} />
        <span>TrimP is running and optimizing your context.</span>
      </div>

      {/* Savings Cards */}
      <div className="savings-cards">
        <div className="savings-card">
          <div className="savings-card-label">
            <DollarSign size={16} />
            Savings this session
          </div>
          <div className="savings-card-value">${(sessionSavings / 1000000 * 3).toFixed(2)}</div>
          <div className="savings-card-sub">{sessionSavings.toLocaleString()} tokens</div>
        </div>

        <div className="savings-card">
          <div className="savings-card-label">
            <Zap size={16} />
            Token savings
          </div>
          <div className="savings-card-value">
            {allTimeSavings > 1000000 
              ? `${(allTimeSavings / 1000000).toFixed(1)}M`
              : `${(allTimeSavings / 1000).toFixed(1)}K`}
          </div>
          <div className="savings-card-sub">{savingsPercent}% reduction</div>
        </div>

        <div className="savings-card">
          <div className="savings-card-label">
            <TrendingUp size={16} />
            All-time savings
          </div>
          <div className="savings-card-value">${(allTimeSavings / 1000000 * 3).toFixed(0)}</div>
          <div className="savings-card-sub">{(allTimeSavings / 1000000).toFixed(1)}M tokens</div>
        </div>
      </div>

      {/* Recent Compressions mini-feed */}
      {recentComps && recentComps.length > 0 && (
        <div className="chart-container" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', margin: '0 0 0.75rem' }}>
            🕐 Recent Compressions
            <span style={{ fontSize: '0.72rem', fontWeight: 400, opacity: 0.55, marginLeft: '0.25rem' }}>• live</span>
          </h3>
          <div style={{ fontFamily: 'monospace', fontSize: '0.83rem' }}>
            {recentComps.slice(0, 8).map((c, i) => {
              const saved = c.tokens_saved ?? (c.tokens_before - c.tokens_after)
              const pct   = c.tokens_before > 0 ? ((saved / c.tokens_before) * 100).toFixed(1) : 0
              return (
                <div key={i} style={{
                  display: 'grid',
                  gridTemplateColumns: '70px 160px 110px 60px',
                  gap: '0.5rem',
                  padding: '0.3rem 0',
                  borderBottom: '1px solid var(--border)',
                  alignItems: 'center',
                }}>
                  <span style={{ color: 'var(--muted)', fontSize: '0.78rem' }}>
                    {new Date(c.compressed_at).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                  <span style={{ color: 'var(--accent)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.compressor}</span>
                  <span style={{ color: 'var(--muted)', fontSize: '0.78rem' }}>{c.tokens_before}→{c.tokens_after}</span>
                  <span style={{ color: 'var(--green)', fontWeight: 700 }}>{pct}%</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* History Chart */}
      <div className="chart-container">
        <div className="chart-header">
          <h2 className="chart-title">History</h2>
          <div className="chart-controls">
            <button className="chart-btn active">day</button>
            <button className="chart-btn">month</button>
          </div>
        </div>

        {trends && trends.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={trends}>
              <defs>
                <linearGradient id="colorSaved" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#27ae60" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#27ae60" stopOpacity={0.1}/>
                </linearGradient>
                <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#e67e22" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#e67e22" stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
              <XAxis 
                dataKey="day" 
                stroke="#95a5a6" 
                fontSize={11}
                tickFormatter={(val) => new Date(val).getDate()}
              />
              <YAxis stroke="#95a5a6" fontSize={11} />
              <Tooltip 
                contentStyle={{ 
                  background: 'white', 
                  border: '1px solid #e0e0e0',
                  borderRadius: '8px',
                  color: '#2c3e50'
                }}
                formatter={(value) => `${(value / 1000).toFixed(1)}K`}
              />
              <Area 
                type="monotone" 
                dataKey="saved" 
                stroke="#27ae60" 
                fillOpacity={1} 
                fill="url(#colorSaved)" 
                name="Tokens Saved"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>
            <p>No history data yet. Use GitHub Copilot to start tracking savings.</p>
          </div>
        )}
      </div>

      {/* Quick Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <div className="chart-container">
          <h3 style={{ marginBottom: '1rem' }}>Current Session</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <StatRow label="Repository" value={session?.repository || '—'} />
            <StatRow label="Branch" value={session?.branch || '—'} />
            <StatRow label="Quality Grade" value={session?.quality_grade || '?'} valueColor="var(--accent)" />
            <StatRow label="Tokens In" value={session?.total_tokens_in?.toLocaleString() || '0'} />
            <StatRow label="Tokens Out" value={session?.total_tokens_out?.toLocaleString() || '0'} />
            <StatRow label="Tokens Saved" value={sessionSavings.toLocaleString()} valueColor="var(--green)" />
          </div>
        </div>

        <div className="chart-container">
          <h3 style={{ marginBottom: '1rem' }}>Active Features</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <FeatureRow name="Bash Compression"   active={isEnabled('bash')} />
            <FeatureRow name="Search Compression" active={isEnabled('search')} />
            <FeatureRow name="Delta Mode"         active={isEnabled('delta')} />
            <FeatureRow name="Code Skeletons"     active={isEnabled('skeleton')} />
            <FeatureRow name="Archive (>4KB)"     active={isEnabled('archive')} />
            <FeatureRow name="Loop Detection"     active={isEnabled('loop_detect')} />
            <FeatureRow name="Verbosity Nudges"   active={isEnabled('verbosity')} />
            <FeatureRow name="Quality Scoring"    active={true} />
            <FeatureRow name="Activity Mode"      active={isEnabled('activity')} />
          </div>
        </div>
      </div>
    </div>
  )
}

function StatRow({ label, value, valueColor }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>{label}</span>
      <span style={{ fontWeight: '600', color: valueColor || 'var(--text)' }}>{value}</span>
    </div>
  )
}

function FeatureRow({ name, active }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0' }}>
      <div style={{ 
        width: '8px', 
        height: '8px', 
        borderRadius: '50%', 
        background: active ? 'var(--green)' : 'var(--muted)' 
      }} />
      <span style={{ fontSize: '0.9rem', color: 'var(--text)' }}>{name}</span>
    </div>
  )
}
