import React, { useState, useEffect } from 'react';
import { 
  TrendingDown, Zap, Activity, Database, 
  Award, Clock, Info, Calendar, FolderGit, Eye
} from 'lucide-react';

/**
 * CompressionRow - Interactive row with hover tooltip showing compression details
 */
function CompressionRow({ compression, index }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  
  // Parse timestamp
  const date = new Date(compression.compressed_at);
  const time = date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit',
    hour12: true 
  });
  const dayOfWeek = date.toLocaleDateString('en-US', { weekday: 'long' });
  const fullDate = date.toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric' 
  });
  
  // Calculate savings
  const saved = compression.tokens_before - compression.tokens_after;
  const savingsPercent = compression.tokens_before > 0 
    ? ((saved / compression.tokens_before) * 100).toFixed(1)
    : 0;
  
  // Compressor descriptions
  const compressorInfo = {
    'UniversalOptimizer': {
      name: 'Universal Optimizer',
      description: 'Auto-detects input type and routes to the best compression algorithm',
      how: 'Uses heuristic detection (JSON patterns, code keywords, log timestamps) to identify content type, then applies specialized compression',
      when: 'Best for mixed content or when you don\'t know the input type'
    },
    'LLMLinguaLite': {
      name: 'LLMLingua Lite',
      description: 'Self-information pruning - removes low-entropy tokens',
      how: 'Calculates word frequency (self-information) and removes common, low-value words while preserving meaning',
      when: 'Best for long documents, articles, or verbose text'
    },
    'CodeContextTrimmer': {
      name: 'Code Trimmer',
      description: 'U-shape recency scoring for code files',
      how: 'Keeps function definitions, imports, and recently edited lines. Uses structural patterns (def, class, import) to identify critical code',
      when: 'Best for Python, JavaScript, TypeScript, Java files'
    },
    'ConversationCompressor': {
      name: 'Chat Compressor',
      description: 'BM25-based conversation compression',
      how: 'Keeps recent messages verbatim, uses BM25 relevance scoring for middle messages, summarizes old messages',
      when: 'Best for long chat histories with multiple turns'
    },
    'JSONMinimizer': {
      name: 'JSON Minimizer',
      description: 'Removes whitespace and unnecessary fields',
      how: 'Whitelists important keys (id, name, error), samples large arrays, removes nulls, compact serialization',
      when: 'Best for API responses, config files, data dumps'
    },
    'LogExtractor': {
      name: 'Log Extractor',
      description: 'Extracts errors and critical log entries',
      how: 'Classifies log levels (ERROR > WARN > INFO), deduplicates repeated messages, keeps context around errors',
      when: 'Best for server logs, stack traces, build output'
    }
  };
  
  const info = compressorInfo[compression.compressor] || {
    name: compression.compressor,
    description: 'Custom compression algorithm',
    how: 'Applies specialized compression rules',
    when: 'Context-specific optimization'
  };
  
  return (
    <tr 
      className="compression-row"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      style={{ position: 'relative' }}
    >
      <td>
        <div className="time-cell">
          <div className="time">{time}</div>
          <div className="date-info">{dayOfWeek}, {fullDate}</div>
          {compression.repository && (
            <div className="repo-info">
              <FolderGit size={12} />
              <span>{compression.repository}</span>
            </div>
          )}
        </div>
      </td>
      
      <td>
        <div className="compressor-cell">
          <span className="compressor-name">{info.name}</span>
          <Info 
            size={14} 
            className="info-icon"
            style={{ marginLeft: '6px', cursor: 'help', color: 'var(--hpe-primary)' }}
          />
        </div>
        
        {showTooltip && (
          <div className="compression-tooltip">
            <div className="tooltip-header">
              <strong>{info.name}</strong>
            </div>
            <div className="tooltip-section">
              <strong>What it does:</strong>
              <p>{info.description}</p>
            </div>
            <div className="tooltip-section">
              <strong>How it works:</strong>
              <p>{info.how}</p>
            </div>
            <div className="tooltip-section">
              <strong>When to use:</strong>
              <p>{info.when}</p>
            </div>
            <div className="tooltip-section">
              <strong>Token calculation:</strong>
              <p>
                Before: {compression.tokens_before} tokens (≈{(compression.tokens_before * 4).toLocaleString()} chars)
                <br />
                After: {compression.tokens_after} tokens (≈{(compression.tokens_after * 4).toLocaleString()} chars)
                <br />
                <strong>Saved: {saved} tokens ({savingsPercent}%)</strong>
              </p>
            </div>
          </div>
        )}
      </td>
      
      <td className="number-cell">{compression.tokens_before.toLocaleString()}</td>
      <td className="number-cell">{compression.tokens_after.toLocaleString()}</td>
      <td className="number-cell savings-cell">
        {saved.toLocaleString()}
      </td>
      <td className="number-cell">
        <span className="savings-badge" style={{
          background: savingsPercent >= 60 ? 'var(--hpe-primary)' : 
                     savingsPercent >= 40 ? 'var(--hpe-blue)' : 
                     'var(--hpe-purple)'
        }}>
          {savingsPercent}%
        </span>
      </td>
      <td className="preview-cell">
        <button
          className="preview-button"
          onClick={() => setShowPreview(!showPreview)}
          title="View compression details"
        >
          <Eye size={16} />
          {showPreview ? 'Hide' : 'Preview'}
        </button>
        
        {showPreview && compression.original_text && (
          <div className="preview-modal">
            <div className="preview-content">
              <h4>Original Text (First 200 chars)</h4>
              <pre>{compression.original_text.substring(0, 200)}...</pre>
              
              {compression.compressed_text && (
                <>
                  <h4>Compressed Text (First 200 chars)</h4>
                  <pre>{compression.compressed_text.substring(0, 200)}...</pre>
                </>
              )}
              
              <div className="preview-stats">
                <div>Original: {compression.tokens_before} tokens</div>
                <div>Compressed: {compression.tokens_after} tokens</div>
                <div>Saved: {saved} tokens ({savingsPercent}%)</div>
              </div>
              
              <button
                className="close-preview"
                onClick={() => setShowPreview(false)}
              >
                Close
              </button>
            </div>
          </div>
        )}
      </td>
    </tr>
  );
}

/**
 * LiveCompressionTable - Real-time updating compression table
 */
export default function LiveCompressionTable({ autoRefresh = true, refreshInterval = 2000 }) {
  const [compressions, setCompressions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const fetchCompressions = async () => {
    try {
      const response = await fetch('http://localhost:7432/api/compressions/recent?limit=20');
      if (response.ok) {
        const data = await response.json();
        setCompressions(data);
        setLastUpdate(new Date());
      }
    } catch (error) {
      console.error('Failed to fetch compressions:', error);
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    fetchCompressions();
    
    if (autoRefresh) {
      const interval = setInterval(fetchCompressions, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval]);
  
  if (loading) {
    return <div className="loading">Loading compressions...</div>;
  }
  
  if (compressions.length === 0) {
    return (
      <div className="no-data">
        <Activity size={48} style={{ opacity: 0.3 }} />
        <p>No compressions yet. Start chatting with Copilot to see compressions appear here!</p>
      </div>
    );
  }
  
  const totalSaved = compressions.reduce((sum, c) => sum + (c.tokens_before - c.tokens_after), 0);
  const avgSavings = compressions.length > 0
    ? (totalSaved / compressions.reduce((sum, c) => sum + c.tokens_before, 0) * 100).toFixed(1)
    : 0;
  
  return (
    <div className="live-compression-table">
      <div className="table-header">
        <div>
          <h2>Real-Time Compression Monitor</h2>
          <p className="table-subtitle">
            Showing {compressions.length} recent compressions
            {lastUpdate && (
              <span className="last-update">
                • Last updated: {lastUpdate.toLocaleTimeString()}
              </span>
            )}
            {autoRefresh && (
              <span className="auto-refresh-badge">
                <Activity size={12} className="spinning" /> Auto-refreshing
              </span>
            )}
          </p>
        </div>
        
        <div className="table-stats">
          <div className="stat-badge">
            <TrendingDown size={16} />
            <span>{totalSaved.toLocaleString()} tokens saved</span>
          </div>
          <div className="stat-badge">
            <Award size={16} />
            <span>{avgSavings}% average savings</span>
          </div>
        </div>
      </div>
      
      <div className="table-wrapper">
        <table className="compressions-table">
          <thead>
            <tr>
              <th>
                <Clock size={14} style={{ marginRight: '6px' }} />
                Time & Date
              </th>
              <th>
                <Zap size={14} style={{ marginRight: '6px' }} />
                Compression Method
              </th>
              <th>Before</th>
              <th>After</th>
              <th>Saved</th>
              <th>%</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {compressions.map((compression, index) => (
              <CompressionRow 
                key={compression.id || index} 
                compression={compression} 
                index={index}
              />
            ))}
          </tbody>
        </table>
      </div>
      
      <style jsx>{`
        .live-compression-table {
          background: var(--surface);
          border-radius: 8px;
          padding: 24px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .table-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 20px;
          flex-wrap: wrap;
          gap: 16px;
        }
        
        .table-header h2 {
          margin: 0;
          color: var(--hpe-primary);
          font-size: 24px;
          font-weight: 600;
        }
        
        .table-subtitle {
          margin: 4px 0 0 0;
          color: var(--text-muted);
          font-size: 14px;
        }
        
        .last-update {
          margin-left: 8px;
          opacity: 0.7;
        }
        
        .auto-refresh-badge {
          margin-left: 12px;
          padding: 2px 8px;
          background: var(--hpe-primary);
          color: white;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 500;
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }
        
        .spinning {
          animation: spin 2s linear infinite;
        }
        
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        
        .table-stats {
          display: flex;
          gap: 12px;
        }
        
        .stat-badge {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 12px;
          background: var(--hpe-primary-light);
          border-radius: 6px;
          color: var(--hpe-primary);
          font-weight: 500;
          font-size: 14px;
        }
        
        .table-wrapper {
          overflow-x: auto;
          border-radius: 6px;
          border: 1px solid var(--border);
        }
        
        .compressions-table {
          width: 100%;
          border-collapse: collapse;
          background: var(--surface-elevated);
        }
        
        .compressions-table thead {
          background: var(--hpe-blue-dark);
          color: white;
        }
        
        .compressions-table th {
          padding: 12px 16px;
          text-align: left;
          font-weight: 600;
          font-size: 13px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          display: flex;
          align-items: center;
        }
        
        .compression-row {
          border-bottom: 1px solid var(--border);
          transition: background 0.2s ease;
          cursor: pointer;
        }
        
        .compression-row:hover {
          background: var(--hpe-primary-light);
        }
        
        .compression-row td {
          padding: 12px 16px;
        }
        
        .time-cell {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        
        .time {
          font-weight: 600;
          font-size: 14px;
          color: var(--text-primary);
        }
        
        .date-info {
          font-size: 12px;
          color: var(--text-muted);
        }
        
        .repo-info {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 11px;
          color: var(--hpe-blue);
          margin-top: 2px;
        }
        
        .compressor-cell {
          display: flex;
          align-items: center;
          position: relative;
        }
        
        .compressor-name {
          font-weight: 500;
          color: var(--text-primary);
        }
        
        .info-icon {
          opacity: 0.6;
          transition: opacity 0.2s;
        }
        
        .compression-row:hover .info-icon {
          opacity: 1;
        }
        
        .compression-tooltip {
          position: absolute;
          top: 100%;
          left: 0;
          z-index: 1000;
          background: white;
          border: 2px solid var(--hpe-primary);
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          max-width: 400px;
          margin-top: 8px;
        }
        
        .tooltip-header {
          color: var(--hpe-primary);
          font-size: 16px;
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid var(--border);
        }
        
        .tooltip-section {
          margin-bottom: 12px;
        }
        
        .tooltip-section strong {
          display: block;
          color: var(--hpe-blue);
          font-size: 12px;
          text-transform: uppercase;
          margin-bottom: 4px;
          letter-spacing: 0.5px;
        }
        
        .tooltip-section p {
          margin: 0;
          font-size: 13px;
          line-height: 1.5;
          color: var(--text-primary);
        }
        
        .number-cell {
          text-align: right;
          font-variant-numeric: tabular-nums;
          font-weight: 500;
        }
        
        .savings-cell {
          color: var(--hpe-primary);
          font-weight: 600;
        }
        
        .savings-badge {
          padding: 4px 8px;
          border-radius: 4px;
          color: white;
          font-size: 12px;
          font-weight: 600;
        }
        
        .preview-cell {
          text-align: center;
        }
        
        .preview-button {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 6px 12px;
          background: var(--hpe-blue);
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
          font-weight: 500;
          transition: background 0.2s;
        }
        
        .preview-button:hover {
          background: var(--hpe-blue-dark);
        }
        
        .preview-modal {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0,0,0,0.7);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 2000;
          padding: 20px;
        }
        
        .preview-content {
          background: white;
          border-radius: 8px;
          padding: 24px;
          max-width: 800px;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }
        
        .preview-content h4 {
          color: var(--hpe-primary);
          margin: 16px 0 8px 0;
          font-size: 14px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        
        .preview-content pre {
          background: var(--surface);
          padding: 12px;
          border-radius: 4px;
          font-size: 12px;
          line-height: 1.6;
          overflow-x: auto;
          border: 1px solid var(--border);
        }
        
        .preview-stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          margin: 16px 0;
          padding: 12px;
          background: var(--hpe-primary-light);
          border-radius: 6px;
        }
        
        .preview-stats div {
          font-size: 13px;
          font-weight: 500;
          color: var(--hpe-primary);
        }
        
        .close-preview {
          width: 100%;
          padding: 10px;
          background: var(--hpe-blue);
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-weight: 500;
          margin-top: 16px;
        }
        
        .close-preview:hover {
          background: var(--hpe-blue-dark);
        }
        
        .no-data {
          text-align: center;
          padding: 60px 20px;
          color: var(--text-muted);
        }
        
        .no-data p {
          margin-top: 16px;
          font-size: 16px;
        }
        
        .loading {
          text-align: center;
          padding: 40px;
          color: var(--text-muted);
        }
      `}</style>
    </div>
  );
}
