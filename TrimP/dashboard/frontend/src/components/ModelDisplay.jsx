import React from 'react';
import { Cpu, Zap, Brain } from 'lucide-react';

/**
 * ModelBadge - Display model information with HPE branding
 */
export function ModelBadge({ model = 'Claude Sonnet 4.5', size = 'md' }) {
  const modelInfo = getModelInfo(model);
  
  const sizeClasses = {
    sm: 'badge-sm',
    md: 'badge-md',
    lg: 'badge-lg',
  };

  return (
    <div className={`model-badge ${sizeClasses[size]}`} style={{ background: modelInfo.color }}>
      <modelInfo.icon size={size === 'sm' ? 12 : size === 'lg' ? 18 : 14} />
      <span>{modelInfo.shortName}</span>
      
      <style jsx>{`
        .model-badge {
          display: inline-flex;
          align-items: center;
          gap: var(--space-xs);
          padding: var(--space-xs) var(--space-sm);
          border-radius: var(--radius-sm);
          font-weight: 500;
          color: white;
          white-space: nowrap;
        }

        .badge-sm {
          font-size: var(--text-xs);
          padding: 2px var(--space-xs);
        }

        .badge-md {
          font-size: var(--text-sm);
        }

        .badge-lg {
          font-size: var(--text-base);
          padding: var(--space-sm) var(--space);
        }
      `}</style>
    </div>
  );
}

/**
 * ModelComparison - Compare statistics across models
 */
export function ModelComparison({ stats = [] }) {
  if (!stats || stats.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">
            <Brain size={20} />
            Model Comparison
          </h3>
        </div>
        <p className="text-muted">No model data available yet.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          <Brain size={20} />
          Model Comparison
        </h3>
        <p className="card-subtitle">{stats.length} models used</p>
      </div>
      
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>Compressions</th>
              <th>Tokens Saved</th>
              <th>Savings %</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((stat) => {
              const modelInfo = getModelInfo(stat.model_used);
              return (
                <tr key={stat.model_used}>
                  <td>
                    <ModelBadge model={stat.model_used} size="sm" />
                  </td>
                  <td>{stat.compressions?.toLocaleString() || 0}</td>
                  <td className="font-mono">{stat.tokens_saved?.toLocaleString() || 0}</td>
                  <td>
                    <span className="text-primary font-bold">
                      {stat.savings_pct || 0}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * ModelFilter - Filter by model
 */
export function ModelFilter({ models = [], selected = 'all', onChange }) {
  return (
    <div className="model-filter">
      <label className="filter-label">
        <Brain size={14} />
        Filter by Model
      </label>
      
      <select
        className="filter-select"
        value={selected}
        onChange={(e) => onChange && onChange(e.target.value)}
      >
        <option value="all">All Models</option>
        {models.map((model) => (
          <option key={model} value={model}>
            {getModelInfo(model).shortName}
          </option>
        ))}
      </select>
      
      <style jsx>{`
        .model-filter {
          display: flex;
          align-items: center;
          gap: var(--space);
        }

        .filter-label {
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          font-size: var(--text-sm);
          color: var(--text-muted);
          font-weight: 500;
        }

        .filter-select {
          padding: var(--space-sm) var(--space);
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          color: var(--text);
          font-size: var(--text-sm);
          font-family: inherit;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .filter-select:hover {
          border-color: var(--hpe-primary);
        }

        .filter-select:focus {
          outline: none;
          border-color: var(--hpe-primary);
          box-shadow: 0 0 0 3px rgba(1, 169, 130, 0.1);
        }
      `}</style>
    </div>
  );
}

// Helper function to get model info
function getModelInfo(modelName) {
  const name = (modelName || '').toLowerCase();
  
  if (name.includes('claude') && name.includes('sonnet')) {
    return {
      shortName: 'Sonnet',
      fullName: 'Claude Sonnet 4.5',
      icon: Brain,
      color: '#7630EA',
    };
  }
  
  if (name.includes('claude') && name.includes('opus')) {
    return {
      shortName: 'Opus',
      fullName: 'Claude Opus',
      icon: Brain,
      color: '#FF8300',
    };
  }
  
  if (name.includes('claude') && name.includes('haiku')) {
    return {
      shortName: 'Haiku',
      fullName: 'Claude Haiku',
      icon: Zap,
      color: '#5FCBEB',
    };
  }
  
  if (name.includes('gpt')) {
    return {
      shortName: 'GPT-4',
      fullName: 'GPT-4',
      icon: Cpu,
      color: '#01A982',
    };
  }
  
  return {
    shortName: 'Unknown',
    fullName: modelName || 'Unknown Model',
    icon: Cpu,
    color: '#425563',
  };
}
