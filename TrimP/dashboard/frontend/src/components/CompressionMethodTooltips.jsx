import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, Info } from 'lucide-react';

/**
 * CompressionMethodTooltips - User-friendly tooltips for all compression modes
 */
export default function CompressionMethodTooltips() {
  const [expandedMode, setExpandedMode] = useState(null);

  // User-friendly descriptions for each compression mode
  const compressionModes = [
    {
      mode: 'universal',
      title: 'Universal (Auto-Detect)',
      icon: '🎯',
      description: 'Automatically detects input type and chooses the best compression algorithm',
      when: 'Use when you don\'t know what type of content you have',
      example: 'Mixed content with code, JSON, logs, etc.',
      savings: '40-60%',
      command: 'TrimP compress --mode universal'
    },
    {
      mode: 'code',
      title: 'Code Compression',
      icon: '💻',
      description: 'Optimizes source code by keeping important parts (functions, imports) and trimming less relevant sections',
      when: 'Use for Python, JavaScript, Java, or any programming language files',
      example: 'app.py, main.js, Component.tsx',
      savings: '40-75%',
      command: 'TrimP compress --mode code'
    },
    {
      mode: 'conversation',
      title: 'Chat/Conversation',
      icon: '💬',
      description: 'Compresses long chat histories using BM25 algorithm. Keeps recent messages intact, summarizes old ones',
      when: 'Use for long conversation threads or chat logs',
      example: 'Multi-turn dialogues, support chat transcripts',
      savings: '55-70%',
      command: 'TrimP compress --mode conversation'
    },
    {
      mode: 'json',
      title: 'JSON/API Responses',
      icon: '📦',
      description: 'Removes unnecessary fields, samples large arrays, and compacts structure while keeping important data',
      when: 'Use for API responses, configuration files, data dumps',
      example: '{"users": [...], "metadata": {...}}',
      savings: '60-90%',
      command: 'TrimP compress --mode json'
    },
    {
      mode: 'log',
      title: 'Logs & Traces',
      icon: '📋',
      description: 'Extracts errors and warnings, removes duplicate lines, keeps context around important events',
      when: 'Use for server logs, stack traces, application logs',
      example: 'server.log, error.log, trace output',
      savings: '50-80%',
      command: 'TrimP compress --mode log'
    },
    {
      mode: 'bash',
      title: 'Command Line Output',
      icon: '⚡',
      description: 'Compresses CLI output from git, tests, builds, and other commands. Removes verbose progress bars',
      when: 'Use for terminal output, build logs, test results',
      example: 'git log, npm test, pytest output',
      savings: '50-80%',
      command: 'TrimP compress --mode bash'
    },
    {
      mode: 'search',
      title: 'Search Results',
      icon: '🔍',
      description: 'Shows top matches and counts rest. Removes duplicate file paths',
      when: 'Use for grep/ripgrep output, file search results',
      example: 'grep "error" *.log, rg "TODO"',
      savings: '60-85%',
      command: 'TrimP compress --mode search'
    },
    {
      mode: 'prompt',
      title: 'Prompt/Instructions',
      icon: '📝',
      description: 'Simplifies verbose prompts and instructions, removes filler words',
      when: 'Use for long user prompts or system instructions',
      example: 'User queries with lots of explanation',
      savings: '30-50%',
      command: 'TrimP compress --mode prompt'
    },
    {
      mode: 'lingua',
      title: 'LLMLingua (Generic Text)',
      icon: '📄',
      description: 'Uses self-information scoring to remove low-value words while keeping meaning',
      when: 'Use for any long text document or article',
      example: 'Documentation, articles, long descriptions',
      savings: '30-60%',
      command: 'TrimP compress --mode lingua'
    },
    {
      mode: 'delta',
      title: 'Delta (File Changes)',
      icon: '🔄',
      description: 'For file re-reads, shows only what changed (diff) instead of full content',
      when: 'Use when re-reading same file multiple times',
      example: 'Editing a file in a loop',
      savings: '80-95%',
      command: 'TrimP compress --mode delta'
    },
    {
      mode: 'skeleton',
      title: 'Code Structure Map',
      icon: '🏗️',
      description: 'Creates outline of code showing functions, classes, imports without full implementation',
      when: 'Use to understand code structure without all details',
      example: 'Large codebases, architecture overview',
      savings: '70-90%',
      command: 'TrimP compress --mode skeleton'
    },
    {
      mode: 'stopword',
      title: 'Stop-Word Removal',
      icon: '🚫',
      description: 'Removes common filler words (the, is, a, etc.) that don\'t add meaning',
      when: 'Use for cleaning up verbose text',
      example: 'Natural language with lots of filler',
      savings: '10-30%',
      command: 'TrimP compress --mode stopword'
    },
    {
      mode: 'image',
      title: 'Image Descriptions',
      icon: '🖼️',
      description: 'Replaces long image descriptions with structured templates',
      when: 'Use for screenshots, diagrams, visual content',
      example: 'Screenshot descriptions, UI mockups',
      savings: '85-92%',
      command: 'TrimP compress --mode image'
    },
    {
      mode: 'architecture',
      title: 'Architecture Docs',
      icon: '🏛️',
      description: 'Extracts component relationships and interfaces from design documents',
      when: 'Use for system design docs, architecture diagrams',
      example: 'Design docs, RFC documents',
      savings: '60-80%',
      command: 'TrimP compress --mode architecture'
    },
    {
      mode: 'mcp',
      title: 'MCP Tool Schemas',
      icon: '🔧',
      description: 'Compresses MCP tool definitions, keeping only relevant tool descriptions',
      when: 'Use for agent tool registrations',
      example: 'MCP server tool schemas',
      savings: '60-90%',
      command: 'TrimP compress --mode mcp'
    }
  ];

  return (
    <div className="compression-tooltips">
      <div className="section-header">
        <h2>📚 Compression Methods Guide</h2>
        <p className="text-muted">Click any method to learn more</p>
      </div>

      <div className="methods-grid">
        {compressionModes.map((method, index) => (
          <div 
            key={method.mode}
            className={`method-card ${expandedMode === index ? 'expanded' : ''}`}
            onClick={() => setExpandedMode(expandedMode === index ? null : index)}
          >
            <div className="card-header">
              <span className="method-icon">{method.icon}</span>
              <div className="method-title">
                <h3>{method.title}</h3>
                <span className="mode-badge">{method.mode}</span>
              </div>
              {expandedMode === index ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </div>

            <p className="method-description">{method.description}</p>

            {expandedMode === index && (
              <div className="method-details">
                <div className="detail-row">
                  <strong>💡 When to Use:</strong>
                  <p>{method.when}</p>
                </div>
                
                <div className="detail-row">
                  <strong>📌 Example:</strong>
                  <code>{method.example}</code>
                </div>

                <div className="detail-row">
                  <strong>📊 Typical Savings:</strong>
                  <span className="savings-badge">{method.savings}</span>
                </div>

                <div className="detail-row">
                  <strong>⚡ Command:</strong>
                  <code className="command">{method.command}</code>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <style jsx>{`
        .compression-tooltips {
          padding: var(--space-xl);
          background: var(--bg-elevated);
          border-radius: var(--radius-lg);
          margin-top: var(--space-xl);
        }

        .section-header {
          margin-bottom: var(--space-xl);
          text-align: center;
        }

        .section-header h2 {
          font-size: var(--text-2xl);
          margin-bottom: var(--space-sm);
        }

        .methods-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
          gap: var(--space-lg);
        }

        .method-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: var(--space-lg);
          cursor: pointer;
          transition: all var(--transition-base);
        }

        .method-card:hover {
          background: var(--surface-hover);
          border-color: var(--hpe-primary);
          transform: translateY(-2px);
          box-shadow: var(--shadow-lg);
        }

        .method-card.expanded {
          border-color: var(--hpe-primary);
          background: var(--surface-hover);
        }

        .card-header {
          display: flex;
          align-items: center;
          gap: var(--space);
          margin-bottom: var(--space);
        }

        .method-icon {
          font-size: var(--text-2xl);
        }

        .method-title {
          flex: 1;
        }

        .method-title h3 {
          font-size: var(--text-lg);
          margin: 0;
          color: var(--text);
        }

        .mode-badge {
          display: inline-block;
          background: var(--hpe-blue);
          color: var(--text);
          padding: 2px 8px;
          border-radius: 4px;
          font-size: var(--text-xs);
          font-family: var(--font-mono);
          margin-top: var(--space-xs);
        }

        .method-description {
          color: var(--text-muted);
          font-size: var(--text-sm);
          line-height: var(--line-height-relaxed);
          margin: var(--space) 0;
        }

        .method-details {
          margin-top: var(--space-lg);
          padding-top: var(--space-lg);
          border-top: 1px solid var(--border);
          display: flex;
          flex-direction: column;
          gap: var(--space);
        }

        .detail-row {
          display: flex;
          flex-direction: column;
          gap: var(--space-xs);
        }

        .detail-row strong {
          color: var(--hpe-primary);
          font-size: var(--text-sm);
        }

        .detail-row p {
          color: var(--text-muted);
          font-size: var(--text-sm);
          margin: 0;
        }

        .detail-row code {
          background: var(--bg);
          padding: var(--space-xs) var(--space-sm);
          border-radius: var(--radius-sm);
          font-family: var(--font-mono);
          font-size: var(--text-sm);
          color: var(--hpe-blue-light);
        }

        .detail-row code.command {
          color: var(--hpe-primary);
        }

        .savings-badge {
          display: inline-block;
          background: var(--hpe-primary);
          color: var(--bg);
          padding: var(--space-xs) var(--space);
          border-radius: var(--radius-sm);
          font-weight: 600;
          font-size: var(--text-sm);
        }

        @media (max-width: 768px) {
          .methods-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}
