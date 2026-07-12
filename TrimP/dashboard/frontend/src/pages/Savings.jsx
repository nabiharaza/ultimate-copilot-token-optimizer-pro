import { usePolling } from '../hooks/useApi.js'
import { Loading, MetricCard } from '../components/Charts.jsx'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'

const TIERS = [
  { key: 'haiku',  label: 'Claude Haiku',  color: '#58a6ff', rate: '$0.80/1M' },
  { key: 'sonnet', label: 'Claude Sonnet', color: '#3fb950', rate: '$3.00/1M' },
  { key: 'opus',   label: 'Claude Opus',   color: '#bc8cff', rate: '$15.00/1M' },
  { key: 'gpt4',   label: 'GPT-4',         color: '#d29922', rate: '$10.00/1M' },
]

export default function Savings() {
  const { data, loading } = usePolling('/api/savings', 15000)
  const { data: trends } = usePolling('/api/trends/daily?days=30', 60000)

  if (loading && !data) return <Loading />

  const pieData = TIERS.map(t => ({
    name: t.label,
    value: parseFloat((data?.savings?.[t.key] ?? 0).toFixed(6)),
    color: t.color,
  }))

  const totalSaved = data?.tokens_saved ?? 0
  const monthly30 = (trends || []).reduce((s, d) => s + (d.saved ?? 0), 0)

  return (
    <div>
      <div className="metric-grid">
        <MetricCard label="All-time Tokens Saved" value={totalSaved.toLocaleString()} color="var(--green)" />
        <MetricCard label="Last 30 Days" value={monthly30.toLocaleString()} color="var(--accent)" />
        {TIERS.map(t => (
          <MetricCard key={t.key} label={`${t.label} Savings`}
            value={`$${(data?.savings?.[t.key] ?? 0).toFixed(4)}`}
            color={t.color} sub={t.rate} />
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <div className="card">
          <h2>Savings by Model Tier</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: $${value.toFixed(4)}`} labelLine={false}>
                {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip formatter={(v) => `$${v.toFixed(6)}`} contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2>Pricing Reference</h2>
          <table>
            <thead><tr><th>Model</th><th>Rate</th><th>$ Saved</th><th>Annualized (52x)</th></tr></thead>
            <tbody>
              {TIERS.map(t => {
                const saved = data?.savings?.[t.key] ?? 0
                return (
                  <tr key={t.key}>
                    <td style={{ color: t.color }}>{t.label}</td>
                    <td style={{ color: 'var(--muted)' }}>{t.rate}</td>
                    <td style={{ color: 'var(--green)' }}>${saved.toFixed(4)}</td>
                    <td>~${(saved * 52).toFixed(2)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p style={{ color: 'var(--muted)', fontSize: '0.75rem', marginTop: '1rem' }}>
            Annualized estimate assumes 52 sessions/year at current savings rate.
          </p>
        </div>
      </div>
    </div>
  )
}
