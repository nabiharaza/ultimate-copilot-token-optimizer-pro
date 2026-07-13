import React, { useState, useEffect } from 'react';
import { 
  Terminal, Search, Code, FileCode, Filter, MessageSquare,
  Zap, MessageCircle, AlertCircle, Image, Box, Layers,
  Minimize2, Tool, HelpCircle
} from 'lucide-react';

/**
 * CompressionMethodCards - Visual cards explaining each compression method
 */
export default function CompressionMethodCards() {
  const [methods, setMethods] = useState([]);
  const [selectedMethod, setSelectedMethod] = useState(null);

  useEffect(() => {
    fetchMethods();
  }, []);

  const fetchMethods = async () => {
    try {
      const response = await fetch('/api/compression/methods');
      if (response.ok) {
        const data = await response.json();
        setMethods(data);
      }
    } catch (error) {
      console.error('Failed to fetch methods:', error);
      // Fallback to static data
      setMethods(getDefaultMethods());
    }
  };

  return (
    <div className="compression-methods">
      <div className="methods-header">
        <h2>Compression Methods</h2>
        <p className="text-muted">
          {methods.length} algorithms working automatically to optimize your token usage
        </p>
      </div>

      <div className="methods-grid">
        {methods.map((method) => (
          <MethodCard
            key={method.id}
            method={method}
            onClick={() => setSelectedMethod(method)}
          />
        ))}
      </div>

      {selectedMethod && (
        <MethodModal
          method={selectedMethod}
          onClose={() => setSelectedMethod(null)}
        />
      )}

      <style jsx>{`
        .compression-methods {
          margin-bottom: var(--space-2xl);
        }

        .methods-header {
          margin-bottom: var(--space-xl);
        }

        .methods-header h2 {
          margin-bottom: var(--space-sm);
        }

        .methods-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: var(--space-lg);
        }
      `}</style>
    </div>
  );
}

/**
 * MethodCard - Individual compression method card
 */
function MethodCard({ method, onClick }) {
  const Icon = getIcon(method.icon);
  
  return (
    <div className="method-card" onClick={onClick}>
      <div className="method-icon" style={{ background: method.color }}>
        <Icon size={24} />
      </div>
      
      <div className="method-content">
        <h3 className="method-name">{method.name}</h3>
        <p className="method-description">{method.description}</p>
      </div>

      <div className="method-footer">
        <button className="learn-more">
          <HelpCircle size={14} />
          Learn More
        </button>
      </div>

      <style jsx>{`
        .method-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          padding: var(--space-lg);
          cursor: pointer;
          transition: all var(--transition-base);
          display: flex;
          flex-direction: column;
          gap: var(--space);
        }

        .method-card:hover {
          border-color: ${method.color};
          transform: translateY(-4px);
          box-shadow: var(--shadow-lg);
        }

        .method-icon {
          width: 48px;
          height: 48px;
          border-radius: var(--radius);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          margin-bottom: var(--space-sm);
        }

        .method-content {
          flex: 1;
        }

        .method-name {
          font-size: var(--text-lg);
          font-weight: 600;
          margin-bottom: var(--space-xs);
          color: var(--text);
        }

        .method-description {
          font-size: var(--text-sm);
          color: var(--text-muted);
          line-height: var(--line-height-relaxed);
        }

        .method-footer {
          display: flex;
          justify-content: flex-end;
        }

        .learn-more {
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          padding: var(--space-xs) var(--space-sm);
          background: transparent;
          border: none;
          color: ${method.color};
          font-size: var(--text-sm);
          font-weight: 500;
          cursor: pointer;
          border-radius: var(--radius);
          transition: background var(--transition-fast);
          font-family: inherit;
        }

        .learn-more:hover {
          background: var(--surface-hover);
        }
      `}</style>
    </div>
  );
}

/**
 * MethodModal - Detailed method information modal
 */
function MethodModal({ method, onClose }) {
  const Icon = getIcon(method.icon);
  const details = getMethodDetails(method.id);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="method-icon-large" style={{ background: method.color }}>
            <Icon size={32} />
          </div>
          <div>
            <h2>{method.name}</h2>
            <p className="text-muted">{method.description}</p>
          </div>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="detail-section">
            <h3>How It Works</h3>
            <p>{details.howItWorks}</p>
          </div>

          <div className="detail-section">
            <h3>Best Used For</h3>
            <ul>
              {details.bestFor.map((item, idx) => (
                <li key={idx}>{item}</li>
              ))}
            </ul>
          </div>

          <div className="detail-section">
            <h3>Example</h3>
            <div className="example-grid">
              <div className="example-before">
                <div className="example-label">Before ({details.example.before.length} chars)</div>
                <code>{details.example.before}</code>
              </div>
              <div className="example-arrow">→</div>
              <div className="example-after">
                <div className="example-label">After ({details.example.after.length} chars)</div>
                <code>{details.example.after}</code>
              </div>
            </div>
            <div className="savings-display">
              Saved: {details.example.before.length - details.example.after.length} chars 
              ({Math.round((1 - details.example.after.length / details.example.before.length) * 100)}%)
            </div>
          </div>

          {details.tips && (
            <div className="detail-section">
              <h3>Tips</h3>
              <ul>
                {details.tips.map((tip, idx) => (
                  <li key={idx}>{tip}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <style jsx>{`
          .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: var(--space-xl);
            animation: fadeIn var(--transition-base);
          }

          .modal-content {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-xl);
            max-width: 800px;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: var(--shadow-xl);
          }

          .modal-header {
            display: flex;
            align-items: flex-start;
            gap: var(--space);
            padding: var(--space-xl);
            border-bottom: 1px solid var(--border);
          }

          .method-icon-large {
            width: 64px;
            height: 64px;
            border-radius: var(--radius-lg);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            flex-shrink: 0;
          }

          .modal-header > div {
            flex: 1;
          }

          .close-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 32px;
            line-height: 1;
            cursor: pointer;
            padding: 0;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: var(--radius);
            transition: all var(--transition-fast);
          }

          .close-btn:hover {
            background: var(--surface-hover);
            color: var(--text);
          }

          .modal-body {
            padding: var(--space-xl);
          }

          .detail-section {
            margin-bottom: var(--space-xl);
          }

          .detail-section h3 {
            margin-bottom: var(--space);
            color: var(--text);
          }

          .detail-section p, .detail-section li {
            color: var(--text-muted);
            line-height: var(--line-height-relaxed);
          }

          .detail-section ul {
            list-style: none;
            padding-left: var(--space-lg);
          }

          .detail-section li:before {
            content: "→";
            color: ${method.color};
            font-weight: bold;
            display: inline-block;
            width: 1em;
            margin-left: -1em;
          }

          .example-grid {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: var(--space);
            align-items: center;
            margin-bottom: var(--space);
          }

          .example-label {
            font-size: var(--text-xs);
            color: var(--text-subtle);
            margin-bottom: var(--space-xs);
            font-weight: 600;
          }

          .example-before, .example-after {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: var(--space);
          }

          .example-before code, .example-after code {
            display: block;
            font-family: var(--font-mono);
            font-size: var(--text-xs);
            color: var(--text-muted);
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 150px;
            overflow-y: auto;
          }

          .example-arrow {
            font-size: var(--text-2xl);
            color: ${method.color};
            font-weight: bold;
          }

          .savings-display {
            text-align: center;
            padding: var(--space);
            background: var(--bg-elevated);
            border-radius: var(--radius);
            color: ${method.color};
            font-weight: 600;
          }
        `}</style>
      </div>
    </div>
  );
}

// Helper functions
function getIcon(iconName) {
  const icons = {
    terminal: Terminal,
    search: Search,
    code: Code,
    'file-code': FileCode,
    filter: Filter,
    'message-square': MessageSquare,
    zap: Zap,
    'message-circle': MessageCircle,
    'alert-circle': AlertCircle,
    image: Image,
    box: Box,
    layers: Layers,
    'minimize-2': Minimize2,
    tool: Tool,
  };
  
  return icons[iconName] || Code;
}

function getMethodDetails(methodId) {
  const details = {
    bash: {
      howItWorks: 'Analyzes bash command output and applies 60+ patterns to remove redundant information, compress repeated lines, and extract only essential errors and warnings.',
      bestFor: ['Command output', 'Build logs', 'Test results', 'Error traces'],
      example: {
        before: 'npm test\n✓ test 1 passed\n✓ test 2 passed\n✓ test 3 passed\n...(50 more lines)...\n247 tests passed',
        after: '247 tests passed',
      },
      tips: ['Works automatically on all shell output', 'Preserves errors and warnings', 'Safe for credentials'],
    },
    // Add more method details as needed
  };
  
  return details[methodId] || {
    howItWorks: 'This compression method uses advanced algorithms to reduce token usage while preserving meaning.',
    bestFor: ['Various use cases'],
    example: {
      before: 'Example input text that will be compressed...',
      after: 'Compressed output...',
    },
  };
}

function getDefaultMethods() {
  return [
    { id: 'bash', name: 'Bash Output', description: 'Compresses command output', icon: 'terminal', color: '#01A982' },
    { id: 'code', name: 'Code Context', description: 'U-shape recency for code', icon: 'code', color: '#01A982' },
    { id: 'json', name: 'JSON Minimizer', description: 'Minimizes JSON data', icon: 'code', color: '#5FCBEB' },
  ];
}
