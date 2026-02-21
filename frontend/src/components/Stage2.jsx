import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage2.css';

function formatModelLabel(model) {
  if (!model) return 'Unknown';
  const raw = model.startsWith('openrouter/') ? model.replace('openrouter/', '') : model;
  const nice = {
    'anthropic/claude-opus-4.6': 'Opus 4.6',
    'anthropic/claude-sonnet-4.6': 'Sonnet 4.6',
    'anthropic/claude-haiku-4.5': 'Haiku 4.5',
    'google/gemini-3.1-pro-preview': 'Gemini 3.1 Pro Preview',
    'google/gemini-2.5-pro': 'Gemini 2.5 Pro',
    'x-ai/grok-4': 'Grok 4',
    'x-ai/grok-4.1-fast': 'Grok 4.1 Fast',
    'openai/gpt-5.2': 'GPT-5.2',
    'openai/gpt-5.2-chat': 'GPT-5.2 Chat',
    'openai/gpt-5.2-pro': 'GPT-5.2 Pro',
  };
  return nice[raw] || raw;
}

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Replace each "Response X" with the actual model name
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = formatModelLabel(model);
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, defaultCollapsed = false }) {
  const [activeTab, setActiveTab] = useState(0);
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  if (!rankings || rankings.length === 0) {
    return null;
  }

  return (
    <div className="stage stage2">
      <button className="collapse-toggle" onClick={() => setCollapsed((v) => !v)}>
        {collapsed ? '▸' : '▾'} Stage 2: Peer Rankings
      </button>

      {!collapsed && (
        <>
          <h4>Raw Evaluations</h4>
          <p className="stage-description">
            Each model evaluated all responses (anonymized as Response A, B, C, etc.) and provided rankings.
            Below, model names are shown in <strong>bold</strong> for readability, but the original evaluation used anonymous labels.
          </p>

          <div className="tabs">
            {rankings.map((rank, index) => (
              <button
                key={index}
                className={`tab ${activeTab === index ? 'active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {formatModelLabel(rank.model)}
              </button>
            ))}
          </div>

          <div className="tab-content">
            <div className="ranking-model">
              {formatModelLabel(rankings[activeTab].model)}
            </div>
            <div className="ranking-content markdown-content">
              <ReactMarkdown>
                {deAnonymizeText(rankings[activeTab].ranking, labelToModel)}
              </ReactMarkdown>
            </div>

            {rankings[activeTab].parsed_ranking &&
             rankings[activeTab].parsed_ranking.length > 0 && (
              <div className="parsed-ranking">
                <strong>Extracted Ranking:</strong>
                <ol>
                  {rankings[activeTab].parsed_ranking.map((label, i) => (
                    <li key={i}>
                      {labelToModel && labelToModel[label]
                        ? formatModelLabel(labelToModel[label])
                        : label}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>

          {aggregateRankings && aggregateRankings.length > 0 && (() => {
            const medals = ['🥇', '🥈', '🥉'];
            const worst = Math.max(...aggregateRankings.map((a) => a.average_rank));
            const best = Math.min(...aggregateRankings.map((a) => a.average_rank));
            const range = worst - best || 1;
            return (
              <div className="aggregate-rankings">
                <h4>Aggregate Rankings</h4>
                <p className="stage-description">
                  Combined results across all peer evaluations — lower average rank is better.
                </p>
                <div className="aggregate-list">
                  {aggregateRankings.map((agg, index) => {
                    const pct = ((worst - agg.average_rank) / range) * 100;
                    return (
                      <div key={index} className={`aggregate-item ${index < 3 ? 'top-three' : ''}`}>
                        <span className="rank-medal">
                          {index < 3 ? medals[index] : <span className="rank-num">#{index + 1}</span>}
                        </span>
                        <div className="rank-info">
                          <div className="rank-model-row">
                            <span className="rank-model">
                              {formatModelLabel(agg.model)}
                            </span>
                            <span className="rank-score-badge">
                              {agg.average_rank.toFixed(2)}
                            </span>
                          </div>
                          <div className="rank-bar-track">
                            <div
                              className={`rank-bar-fill rank-bar-${index < 3 ? index : 'rest'}`}
                              style={{ width: `${Math.max(pct, 6)}%` }}
                            />
                          </div>
                          <span className="rank-count">
                            {agg.rankings_count} vote{agg.rankings_count !== 1 ? 's' : ''}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()}
        </>
      )}
    </div>
  );
}
