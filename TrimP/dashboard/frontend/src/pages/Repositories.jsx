import { useEffect, useState } from 'react'
import { Boxes, DollarSign, GitBranch, Layers, RefreshCw, Zap } from 'lucide-react'

function n(value) {
  return Number(value || 0).toLocaleString()
}

function money(value) {
  return `$${Number(value || 0).toFixed(4)}`
}

function date(value) {
  return value ? new Date(value).toLocaleString() : '—'
}

function gradeColor(grade) {
  if (grade === 'A') return 'var(--green)'
  if (grade === 'B') return 'var(--accent)'
  if (grade === 'C') return 'var(--yellow)'
  if (grade === 'D') return 'var(--orange)'
  return 'var(--red)'
}

function RepoMetric({ icon: Icon, label, value, sub }) {
  return (
    <div className="repo-metric">
      <Icon size={16} />
      <div>
        <div className="repo-metric-label">{label}</div>
        <div className="repo-metric-value">{value}</div>
        {sub && <div className="repo-metric-sub">{sub}</div>}
      </div>
    </div>
  )
}

export default function Repositories() {
  const [repos, setRepos] = useState([])
  const [selectedRepo, setSelectedRepo] = useState(null)
  const [loading, setLoading] = useState(true)

  async function loadRepositories() {
    setLoading(true)
    try {
      const res = await fetch('/api/repositories')
      const data = await res.json()
      setRepos(data.repositories || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRepositories()
    const id = setInterval(loadRepositories, 5000)
    return () => clearInterval(id)
  }, [])

  return (
    <main className="optimizer-page">
      <header className="optimizer-header">
        <div>
          <div className="optimizer-kicker"><Boxes size={15} /> Repository Analytics</div>
          <h1>Repositories</h1>
          <p>Compression performance by workspace, branch, and model.</p>
        </div>
        <button className="icon-button" onClick={loadRepositories} title="Refresh"><RefreshCw size={16} /></button>
      </header>

      {loading && repos.length === 0 ? (
        <section className="optimizer-panel">Loading repositories...</section>
      ) : repos.length === 0 ? (
        <section className="optimizer-empty">No repository traffic yet. Run `scripts/TrimP-copilot` from a project directory.</section>
      ) : (
        <div className="repo-list">
          {repos.map(repo => (
            <section key={repo.repository} className="repo-card">
              <div className="repo-header">
                <div>
                  <h2>{repo.repository}</h2>
                  <div className="muted">Last request {date(repo.last_session)}</div>
                </div>
                <button className="repo-detail-btn" onClick={() => setSelectedRepo(selectedRepo === repo.repository ? null : repo.repository)}>
                  {selectedRepo === repo.repository ? 'Hide details' : 'Details'}
                </button>
              </div>

              <div className="repo-metrics">
                <RepoMetric icon={Layers} label="Requests" value={n(repo.request_count)} sub={`${n(repo.conversation_count)} conversations`} />
                <RepoMetric icon={Zap} label="Tokens Saved" value={n(repo.tokens_saved)} sub={`${Number(repo.compression_rate || 0).toFixed(2)}% reduction`} />
                <RepoMetric icon={DollarSign} label="Dollars Saved" value={money(repo.dollars_saved)} sub="input estimate" />
                <RepoMetric icon={GitBranch} label="Branches" value={n(repo.branch_count)} sub={(repo.models || []).join(', ') || 'no model'} />
                <div className="repo-grade" style={{ borderColor: gradeColor(repo.avg_grade), color: gradeColor(repo.avg_grade) }}>
                  <span>{repo.avg_grade}</span>
                  <small>compression grade</small>
                </div>
              </div>

              {selectedRepo === repo.repository && (
                <div className="repo-details">
                  <div className="optimizer-panel-title">Branch Savings</div>
                  <div className="repo-branches">
                    {(repo.branches || []).map(branch => (
                      <div className="repo-branch" key={branch.name}>
                        <span>{branch.name}</span>
                        <b>{n(branch.tokens_saved)} saved</b>
                        <small>{n(branch.requests)} requests</small>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          ))}
        </div>
      )}
    </main>
  )
}
