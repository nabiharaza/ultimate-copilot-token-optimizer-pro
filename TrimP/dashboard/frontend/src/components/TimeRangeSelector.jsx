import React, { useState } from 'react';
import { Clock, Calendar } from 'lucide-react';

/**
 * TimeRangeSelector - HPE-branded time range filter
 * 
 * Allows users to filter data by Hour, Day, Week, Month, or All time
 */
export default function TimeRangeSelector({ value = 'all', onChange }) {
  const [activeRange, setActiveRange] = useState(value);

  const ranges = [
    { id: 'hour', label: 'Hour', icon: Clock },
    { id: 'day', label: 'Day', icon: Clock },
    { id: 'week', label: 'Week', icon: Calendar },
    { id: 'month', label: 'Month', icon: Calendar },
    { id: 'all', label: 'All Time', icon: Calendar },
  ];

  const handleChange = (rangeId) => {
    setActiveRange(rangeId);
    if (onChange) {
      onChange(rangeId);
    }
  };

  return (
    <div className="time-range-selector">
      <div className="range-buttons">
        {ranges.map((range) => {
          const Icon = range.icon;
          return (
            <button
              key={range.id}
              className={`range-btn ${activeRange === range.id ? 'active' : ''}`}
              onClick={() => handleChange(range.id)}
            >
              <Icon size={14} />
              <span>{range.label}</span>
            </button>
          );
        })}
      </div>
      
      <style jsx>{`
        .time-range-selector {
          display: inline-flex;
          align-items: center;
          gap: var(--space-sm);
        }

        .range-buttons {
          display: flex;
          gap: var(--space-xs);
          background: var(--surface);
          padding: 4px;
          border-radius: var(--radius);
          border: 1px solid var(--border);
        }

        .range-btn {
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          padding: var(--space-xs) var(--space);
          border: none;
          background: transparent;
          color: var(--text-muted);
          font-size: var(--text-sm);
          font-weight: 500;
          border-radius: calc(var(--radius) - 2px);
          cursor: pointer;
          transition: all var(--transition-fast);
          font-family: inherit;
        }

        .range-btn:hover {
          background: var(--surface-hover);
          color: var(--text);
        }

        .range-btn.active {
          background: var(--hpe-primary);
          color: white;
          box-shadow: var(--shadow-sm);
        }

        .range-btn svg {
          opacity: 0.7;
        }

        .range-btn.active svg {
          opacity: 1;
        }
      `}</style>
    </div>
  );
}
