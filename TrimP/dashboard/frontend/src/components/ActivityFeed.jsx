import React, { useState, useEffect } from 'react';
import { Activity, TrendingDown, Clock, Code, Database } from 'lucide-react';
import { ModelBadge } from './ModelDisplay';

/**
 * ActivityFeed - Real-time compression activity feed
 */
export default function ActivityFeed({ limit = 20, timeRange = 'all' }) {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchActivities();
    const interval = setInterval(fetchActivities, 3000); // Refresh every 3s
    return () => clearInterval(interval);
  }, [limit, timeRange]);

  const fetchActivities = async () => {
    try {
      const response = await fetch(`/api/activity/feed?limit=${limit}`);
      if (response.ok) {
        const data = await response.json();
        setActivities(data);
      }
    } catch (error) {
      console.error('Failed to fetch activity:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card">
        <div className="flex-center" style={{ padding: '2rem' }}>
          <div className="spinner"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="activity-feed">
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">
            <Activity size={20} />
            Live Activity Feed
          </h3>
          <span className="badge badge-primary">
            <div className="pulse-dot"></div>
            Live
          </span>
        </div>

        <div className="activity-list">
          {activities.length === 0 ? (
            <div className="empty-state">
              <Activity size={48} className="text-muted" />
              <p>No activity yet. Start compressing to see results!</p>
            </div>
          ) : (
            activities.map((activity, idx) => (
              <ActivityItem key={idx} activity={activity} />
            ))
          )}
        </div>
      </div>

      <style jsx>{`
        .activity-list {
          display: flex;
          flex-direction: column;
          gap: var(--space);
          max-height: 600px;
          overflow-y: auto;
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: var(--space-2xl);
          gap: var(--space);
          color: var(--text-muted);
        }

        .pulse-dot {
          width: 8px;
          height: 8px;
          background: white;
          border-radius: 50%;
          animation: pulse 2s infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}

/**
 * ActivityItem - Individual activity item
 */
function ActivityItem({ activity }) {
  const [expanded, setExpanded] = useState(false);
  
  const timeAgo = getTimeAgo(activity.compressed_at);
  const method = getCompressionMethod(activity.compressor);

  return (
    <div className="activity-item" onClick={() => setExpanded(!expanded)}>
      <div className="activity-header">
        <div className="activity-icon" style={{ background: method.color }}>
          <method.icon size={16} />
        </div>
        
        <div className="activity-content">
          <div className="activity-title">
            <span className="font-semibold">{method.name}</span>
            <span className="text-muted">compressed {activity.tokens_before?.toLocaleString()} tokens</span>
          </div>
          
          <div className="activity-meta">
            <Clock size={12} />
            <span>{timeAgo}</span>
            
            {activity.model_used && (
              <>
                <span className="meta-divider">•</span>
                <ModelBadge model={activity.model_used} size="sm" />
              </>
            )}
            
            {activity.repo && (
              <>
                <span className="meta-divider">•</span>
                <Database size={12} />
                <span className="font-mono text-xs">{activity.repo.split('/').pop()}</span>
              </>
            )}
          </div>
        </div>
        
        <div className="activity-savings">
          <div className="savings-badge">
            <TrendingDown size={14} />
            <span>{activity.savings_pct}%</span>
          </div>
          <div className="tokens-saved">
            {activity.tokens_saved?.toLocaleString()} saved
          </div>
        </div>
      </div>

      {expanded && (
        <div className="activity-details fade-in">
          <div className="detail-section">
            <div className="detail-label">Original</div>
            <div className="detail-content">
              {activity.original_text ? (
                <code className="code-preview">
                  {activity.original_text.substring(0, 150)}
                  {activity.original_text.length > 150 && '...'}
                </code>
              ) : (
                <span className="text-muted">No preview available</span>
              )}
            </div>
          </div>
          
          <div className="detail-section">
            <div className="detail-label">Compressed</div>
            <div className="detail-content">
              {activity.compressed_text ? (
                <code className="code-preview">
                  {activity.compressed_text.substring(0, 150)}
                  {activity.compressed_text.length > 150 && '...'}
                </code>
              ) : (
                <span className="text-muted">No preview available</span>
              )}
            </div>
          </div>

          <div className="compression-stats">
            <div className="stat-item">
              <span className="stat-label">Before</span>
              <span className="stat-value">{activity.tokens_before?.toLocaleString()}</span>
            </div>
            <div className="stat-divider">→</div>
            <div className="stat-item">
              <span className="stat-label">After</span>
              <span className="stat-value">{activity.tokens_after?.toLocaleString()}</span>
            </div>
            <div className="stat-divider">=</div>
            <div className="stat-item">
              <span className="stat-label">Saved</span>
              <span className="stat-value text-primary">{activity.tokens_saved?.toLocaleString()}</span>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .activity-item {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          padding: var(--space);
          cursor: pointer;
          transition: all var(--transition-base);
        }

        .activity-item:hover {
          border-color: var(--hpe-primary);
          transform: translateY(-1px);
          box-shadow: var(--shadow);
        }

        .activity-header {
          display: flex;
          align-items: center;
          gap: var(--space);
        }

        .activity-icon {
          width: 36px;
          height: 36px;
          border-radius: var(--radius);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          flex-shrink: 0;
        }

        .activity-content {
          flex: 1;
          min-width: 0;
        }

        .activity-title {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          font-size: var(--text-sm);
          margin-bottom: var(--space-xs);
        }

        .activity-meta {
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          font-size: var(--text-xs);
          color: var(--text-subtle);
        }

        .meta-divider {
          opacity: 0.5;
        }

        .activity-savings {
          text-align: right;
          flex-shrink: 0;
        }

        .savings-badge {
          display: inline-flex;
          align-items: center;
          gap: var(--space-xs);
          padding: var(--space-xs) var(--space-sm);
          background: var(--hpe-primary);
          color: white;
          border-radius: var(--radius-sm);
          font-weight: 600;
          font-size: var(--text-sm);
          margin-bottom: var(--space-xs);
        }

        .tokens-saved {
          font-size: var(--text-xs);
          color: var(--text-subtle);
        }

        .activity-details {
          margin-top: var(--space);
          padding-top: var(--space);
          border-top: 1px solid var(--border);
        }

        .detail-section {
          margin-bottom: var(--space);
        }

        .detail-label {
          font-size: var(--text-xs);
          font-weight: 600;
          color: var(--text-subtle);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: var(--space-xs);
        }

        .detail-content {
          font-size: var(--text-sm);
        }

        .code-preview {
          display: block;
          padding: var(--space-sm);
          background: var(--bg-elevated);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          font-family: var(--font-mono);
          font-size: var(--text-xs);
          color: var(--text-muted);
          white-space: pre-wrap;
          word-break: break-all;
        }

        .compression-stats {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space);
          margin-top: var(--space);
          padding: var(--space);
          background: var(--bg-elevated);
          border-radius: var(--radius);
        }

        .stat-item {
          text-align: center;
        }

        .stat-label {
          display: block;
          font-size: var(--text-xs);
          color: var(--text-subtle);
          margin-bottom: var(--space-xs);
        }

        .stat-value {
          display: block;
          font-size: var(--text-lg);
          font-weight: 600;
          font-family: var(--font-mono);
        }

        .stat-divider {
          font-size: var(--text-xl);
          color: var(--text-subtle);
          font-weight: 300;
        }
      `}</style>
    </div>
  );
}

// Helper functions
function getTimeAgo(timestamp) {
  if (!timestamp) return 'just now';
  
  const date = new Date(timestamp);
  const now = new Date();
  const seconds = Math.floor((now - date) / 1000);
  
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function getCompressionMethod(compressor) {
  const methods = {
    bash: { name: 'Bash Output', icon: Code, color: '#01A982' },
    search: { name: 'Search Results', icon: Code, color: '#425563' },
    json: { name: 'JSON', icon: Code, color: '#5FCBEB' },
    code: { name: 'Code Context', icon: Code, color: '#01A982' },
    log: { name: 'Log Extractor', icon: Code, color: '#FF8300' },
    universal: { name: 'Universal', icon: Code, color: '#FFB81C' },
  };
  
  return methods[compressor] || { name: compressor, icon: Code, color: '#7630EA' };
}
