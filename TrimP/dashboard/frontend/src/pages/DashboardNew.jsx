import React, { useState, useEffect } from 'react';
import { 
  TrendingDown, Zap, Activity, Database, 
  Award, Clock
} from 'lucide-react';
import TimeRangeSelector from '../components/TimeRangeSelector';
import { ModelBadge, ModelComparison } from '../components/ModelDisplay';
import ActivityFeed from '../components/ActivityFeed';
import CompressionCards from '../components/CompressionCards';
import CompressionMethodTooltips from '../components/CompressionMethodTooltips';

/**
 * Dashboard - Modern HPE-branded dashboard
 */
export default function Dashboard() {
  const [timeRange, setTimeRange] = useState('all');
  const [stats, setStats] = useState(null);
  const [modelStats, setModelStats] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, [timeRange]);

  const fetchData = async () => {
    try {
      // Fetch current session stats
      const sessionRes = await fetch('/api/session/current');
      if (sessionRes.ok) {
        const sessionData = await sessionRes.json();
        setStats(sessionData);
      }

      // Fetch model stats
      const modelRes = await fetch(`/api/models/stats?range=${timeRange}`);
      if (modelRes.ok) {
        const modelData = await modelRes.json();
        setModelStats(modelData);
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading dashboard...</p>
      </div>
    );
  }

  const totalSaved = stats?.tokens_saved || 0;
  const totalIn = stats?.total_tokens_in || 0;
  const totalOut = stats?.total_tokens_out || 0;
  const savingsPercent = totalIn > 0 ? Math.round((totalSaved / totalIn) * 100) : 0;

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <div>
          <h1>Token Optimizer Dashboard</h1>
          <p className="text-muted">
            Real-time compression analytics • HPE Production Environment
          </p>
        </div>
        
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </div>

      {/* Key Metrics */}
      <div className="metrics-grid">
        <MetricCard
          icon={TrendingDown}
          label="Tokens Saved"
          value={totalSaved.toLocaleString()}
          color="var(--hpe-primary)"
          subtitle={`${savingsPercent}% reduction`}
        />
        
        <MetricCard
          icon={Zap}
          label="Total Processed"
          value={totalIn.toLocaleString()}
          color="var(--hpe-blue-light)"
          subtitle={`${totalOut.toLocaleString()} after compression`}
        />
        
        <MetricCard
          icon={Activity}
          label="Active Models"
          value={modelStats.length}
          color="var(--hpe-purple)"
          subtitle="Currently in use"
        />
        
        <MetricCard
          icon={Award}
          label="Efficiency Score"
          value={`${savingsPercent}%`}
          color="var(--hpe-orange)"
          subtitle="Quality maintained"
        />
      </div>

      {/* Model Comparison */}
      {modelStats.length > 0 && (
        <ModelComparison stats={modelStats} />
      )}

      {/* Activity Feed */}
      <div className="dashboard-section">
        <ActivityFeed limit={20} timeRange={timeRange} />
      </div>

      {/* Compression Methods */}
      <div className="dashboard-section">
        <CompressionMethodTooltips />
      </div>

      {/* Session Info */}
      {stats && (
        <div className="card session-info">
          <div className="card-header">
            <h3 className="card-title">
              <Database size={20} />
              Current Session
            </h3>
          </div>
          
          <div className="session-details">
            <div className="session-item">
              <span className="session-label">Repository</span>
              <span className="session-value font-mono">{stats.repo || 'Unknown'}</span>
            </div>
            <div className="session-item">
              <span className="session-label">Branch</span>
              <span className="session-value font-mono">{stats.branch || 'main'}</span>
            </div>
            <div className="session-item">
              <span className="session-label">Started</span>
              <span className="session-value">
                <Clock size={14} />
                {new Date(stats.started_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .dashboard {
          padding: var(--space-xl);
          max-width: 1600px;
          margin: 0 auto;
        }

        .dashboard-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 60vh;
          gap: var(--space);
          color: var(--text-muted);
        }

        .dashboard-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: var(--space-2xl);
          padding-bottom: var(--space-lg);
          border-bottom: 2px solid var(--border);
        }

        .dashboard-header h1 {
          color: var(--hpe-primary);
          margin-bottom: var(--space-xs);
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: var(--space-lg);
          margin-bottom: var(--space-2xl);
        }

        .dashboard-section {
          margin-bottom: var(--space-2xl);
        }

        .session-info {
          background: var(--bg-elevated);
        }

        .session-details {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: var(--space-lg);
        }

        .session-item {
          display: flex;
          flex-direction: column;
          gap: var(--space-xs);
        }

        .session-label {
          font-size: var(--text-xs);
          color: var(--text-subtle);
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .session-value {
          font-size: var(--text-base);
          color: var(--text);
          display: flex;
          align-items: center;
          gap: var(--space-xs);
        }
      `}</style>
    </div>
  );
}

/**
 * MetricCard - Individual metric display card
 */
function MetricCard({ icon: Icon, label, value, color, subtitle }) {
  return (
    <div className="metric-card">
      <div className="metric-icon" style={{ background: color }}>
        <Icon size={24} />
      </div>
      
      <div className="metric-content">
        <div className="metric-label">{label}</div>
        <div className="metric-value" style={{ color }}>{value}</div>
        {subtitle && <div className="metric-subtitle">{subtitle}</div>}
      </div>

      <style jsx>{`
        .metric-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          padding: var(--space-lg);
          display: flex;
          align-items: center;
          gap: var(--space);
          transition: all var(--transition-base);
        }

        .metric-card:hover {
          transform: translateY(-2px);
          box-shadow: var(--shadow-lg);
          border-color: ${color};
        }

        .metric-icon {
          width: 56px;
          height: 56px;
          border-radius: var(--radius-lg);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          flex-shrink: 0;
        }

        .metric-content {
          flex: 1;
        }

        .metric-label {
          font-size: var(--text-sm);
          color: var(--text-muted);
          margin-bottom: var(--space-xs);
        }

        .metric-value {
          font-size: var(--text-3xl);
          font-weight: 700;
          line-height: 1;
          margin-bottom: var(--space-xs);
        }

        .metric-subtitle {
          font-size: var(--text-xs);
          color: var(--text-subtle);
        }
      `}</style>
    </div>
  );
}
