import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Clock3, Database, RefreshCw, Save, Trash2, X, XCircle } from 'lucide-react'
import { useApi } from '../hooks/useApi.js'
import { Loading } from '../components/Charts.jsx'

export default function Config() {
  const { data: config, loading, refetch } = useApi('/api/config')
  const [saving, setSaving] = useState(null)
  const [editValues, setEditValues] = useState({})
  const [clearOpen, setClearOpen] = useState(false)
  const [confirmation, setConfirmation] = useState('')
  const [clearState, setClearState] = useState(null)
  const [health, setHealth] = useState(null)
  const [saveMessage, setSaveMessage] = useState('')

  async function loadHealth() {
    const response = await fetch('/api/live-health')
    if (response.ok) setHealth(await response.json())
  }

  useEffect(() => {
    loadHealth()
    const timer = setInterval(loadHealth, 5000)
    return () => clearInterval(timer)
  }, [])

  if (loading && !config) return <Loading />

  async function save(key, value) {
    setSaving(key)
    try {
      const response = await fetch(`/api/config/${key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail || 'Could not save setting')
      if (key === 'logs.retention_months') {
        const deleted = result.pruned?.deleted ?? 0
        setSaveMessage(`Retention saved. ${deleted.toLocaleString()} expired record${deleted === 1 ? '' : 's'} removed.`)
      }
      refetch()
    } catch (error) {
      setSaveMessage(error.message)
    } finally {
      setSaving(null)
      setEditValues(v => { const n = {...v}; delete n[key]; return n })
    }
  }

  async function clearDatabase() {
    if (confirmation !== 'CLEAR DB') return
    setClearState('clearing')
    const response = await fetch('/api/database/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmation }),
    })
    const result = await response.json()
    if (result.ok) {
      setClearState('cleared')
      setConfirmation('')
      setTimeout(() => { setClearOpen(false); setClearState(null) }, 900)
    } else setClearState('error')
  }

  const groups = {
    'Compression Features': Object.entries(config || {}).filter(([k]) => k.startsWith('compression.')),
    'Pricing ($/1M tokens)': Object.entries(config || {}).filter(([k]) => k.startsWith('pricing.')),
    'Dashboard': Object.entries(config || {}).filter(([k]) => k.startsWith('dashboard.')),
    'Archive': Object.entries(config || {}).filter(([k]) => k.startsWith('archive.')),
    'Session': Object.entries(config || {}).filter(([k]) => k.startsWith('session.')),
  }
  const retentionValue = editValues['logs.retention_months'] ?? config?.['logs.retention_months'] ?? '6'

  return (
    <div>
      <section className="settings-health-panel">
        <div className="settings-health-header"><div><h2>Live service health</h2><p>Automatic checks for every TrimP dependency and IDE bridge.</p></div><button className="icon-button" onClick={loadHealth} title="Refresh health"><RefreshCw size={16} /></button></div>
        <div className="settings-health-grid">{(health?.services || []).map(service => <div key={service.name} className="settings-health-item"><div className="settings-health-name">{service.status === 'up' ? <CheckCircle2 size={16} /> : <XCircle size={16} />}<b>{service.name}</b></div><span>{service.status === 'up' ? service.detail || 'Running' : service.detail || 'Unavailable'}</span>{service.status !== 'up' && <small>Fix: {service.name === 'BYOK proxy' ? 'python3 byok_server.py --port 8766' : 'restart the IDE bridge and verify proxy settings'}</small>}</div>)}</div>
        <div className="settings-ide-health">{(health?.configured_ides || []).map(ide => <span key={ide.product}><i />{ide.product} · {ide.host}:{ide.port}</span>)}{(!health || health.configured_ides?.length === 0) && <span>No IDE integrations configured</span>}</div>
      </section>
      <section className="developer-panel">
        <div><span className="settings-eyebrow">Release metadata</span><h2>TrimPy v1.0.0</h2><p>Enterprise token optimization system</p></div>
        <div className="release-grid"><span><b>Version</b> 1.0.0</span><span><b>Release</b> Enterprise proxy observability</span><span><b>Runtime</b> GitHub Copilot Enterprise</span></div>
        <details><summary>Developer logs and release notes</summary><pre>TrimP captures request lifecycle, repository and IDE attribution, compression decisions, model usage, cache usage, response metadata, and service health. Release focus: traceability, safe context shaping, and measured cost reduction.</pre></details>
      </section>
      <section className="settings-retention-panel">
        <div className="settings-retention-copy">
          <div className="settings-retention-icon"><Clock3 size={18} /></div>
          <div><span className="settings-eyebrow">Privacy and storage</span><h2>Keep TrimPy logs</h2><p>Choose how long request traces, compression audits, savings history, and imported Copilot usage stay in this local workspace.</p><small>Default: 6 months. Configuration is always preserved. Choosing Forever disables automatic expiry.</small></div>
        </div>
        <div className="settings-retention-controls">
          <label htmlFor="retention-months">Retention period</label>
          <div><select id="retention-months" value={retentionValue} onChange={event => setEditValues(v => ({ ...v, 'logs.retention_months': event.target.value }))}>
            <option value="1">1 month</option><option value="3">3 months</option><option value="6">6 months (recommended)</option><option value="12">12 months</option><option value="24">24 months</option><option value="0">Forever</option>
          </select><button className="retention-save" onClick={() => save('logs.retention_months', retentionValue)} disabled={saving === 'logs.retention_months'}><Save size={14} />{saving === 'logs.retention_months' ? 'Saving…' : 'Save period'}</button></div>
          {saveMessage && <span className="retention-save-message">{saveMessage}</span>}
        </div>
      </section>
      <section className="settings-danger-zone">
        <div>
          <div className="settings-danger-title"><Database size={17} /> Telemetry database</div>
          <p>Remove captured conversations, traces, quality scores, and savings history. Configuration is preserved.</p>
        </div>
        <button className="danger-button" onClick={() => setClearOpen(true)} title="Clear database">
          <Trash2 size={15} /> Clear DB
        </button>
      </section>
      {clearOpen && (
        <div className="confirm-backdrop" role="dialog" aria-modal="true" aria-label="Clear database confirmation">
          <section className="confirm-dialog">
            <button className="confirm-close" onClick={() => setClearOpen(false)} title="Close"><X size={17} /></button>
            <div className="confirm-icon"><AlertTriangle size={22} /></div>
            <h2>Clear DB?</h2>
            <p>This permanently deletes all captured conversations, traces, quality scores, and savings data. This cannot be undone.</p>
            <label>Type <strong>CLEAR DB</strong> to confirm</label>
            <input autoFocus value={confirmation} onChange={e => setConfirmation(e.target.value)} placeholder="CLEAR DB" />
            <div className="confirm-actions">
              <button className="secondary-button" onClick={() => setClearOpen(false)}>Cancel</button>
              <button className="danger-button" disabled={confirmation !== 'CLEAR DB' || clearState === 'clearing'} onClick={clearDatabase}>
                {clearState === 'clearing' ? 'Clearing…' : clearState === 'cleared' ? 'Cleared' : 'Clear DB'}
              </button>
            </div>
          </section>
        </div>
      )}
      {Object.entries(groups).map(([group, entries]) => entries.length === 0 ? null : (
        <div key={group} className="card">
          <h2>{group}</h2>
          <table>
            <thead><tr><th>Key</th><th>Value</th><th>Action</th></tr></thead>
            <tbody>
              {entries.map(([key, val]) => {
                const editVal = editValues[key] ?? val
                const isBool = val === 'true' || val === 'false'
                return (
                  <tr key={key}>
                    <td style={{ fontFamily: 'monospace', color: 'var(--accent)', fontSize: '0.82rem' }}>{key}</td>
                    <td>
                      {isBool ? (
                        <select value={editVal} onChange={e => setEditValues(v => ({...v, [key]: e.target.value}))}
                          style={{ background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 6px' }}>
                          <option value="true">true</option>
                          <option value="false">false</option>
                        </select>
                      ) : (
                        <input value={editVal} onChange={e => setEditValues(v => ({...v, [key]: e.target.value}))}
                          style={{ background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 6px', width: '160px' }} />
                      )}
                    </td>
                    <td>
                      {editValues[key] !== undefined && editValues[key] !== val && (
                        <button onClick={() => save(key, editValues[key])} disabled={saving === key}
                          style={{ background: 'var(--green)', color: '#000', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: '0.8rem' }}>
                          {saving === key ? '…' : 'Save'}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}
