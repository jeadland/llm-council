import { useEffect } from 'react';
import { X } from 'lucide-react';
import MarkdownContent from './MarkdownContent';
import { providerMeta, resolveModelLabel } from '../modelUtils';
import ProviderAvatar from './ProviderAvatar';

const STATE_LABEL = {
  pending: 'Waiting to start',
  thinking: 'Writing its answer…',
  answered: 'Answer ready',
  rating: 'Scoring the council…',
  ranked: 'Rankings submitted',
  winner: 'Top-ranked answer',
  failed: 'No response',
};

function deAnonymize(text, labelToModel, modelMap) {
  if (!text || !labelToModel) return text || '';
  let result = text;
  Object.entries(labelToModel).forEach(([label, model]) => {
    result = result.replace(new RegExp(label, 'g'), `**${resolveModelLabel(model, modelMap)}**`);
  });
  return result;
}

export default function AgentDetail({ agent, labelToModel, modelMap, onClose }) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!agent) return null;

  const meta = providerMeta(agent.model);
  const name = resolveModelLabel(agent.model, modelMap);
  const stage1Text = agent.stage1Row?.response || '';
  const rankingRow = agent.rankingRow || null;
  const rankingText = deAnonymize(rankingRow?.ranking || '', labelToModel, modelMap);
  const parsed = rankingRow?.parsed_ranking || [];

  return (
    <div className="agent-detail-overlay" role="dialog" aria-modal="true" aria-label={`${name} detail`}>
      <button type="button" className="agent-detail-scrim" aria-label="Close" onClick={onClose} />
      <div className="agent-detail-panel">
        <div className="agent-detail-header">
          <ProviderAvatar className="agent-avatar" modelId={agent.model} aria-hidden="true" />
          <div className="agent-detail-heading">
            <h3>{name}</h3>
            <span className="agent-detail-sub">
              {meta.label}
              {agent.rank ? ` · Ranked #${agent.rank}` : ''}
              {typeof agent.averageRank === 'number' ? ` · ${agent.averageRank.toFixed(2)} avg` : ''}
            </span>
          </div>
          <button type="button" className="agent-detail-close" onClick={onClose} aria-label="Close detail">
            <X size={18} />
          </button>
        </div>

        <div className="agent-detail-body">
          <div className="agent-detail-state">{STATE_LABEL[agent.state] || agent.state}</div>

          {stage1Text ? (
            <section className="agent-detail-section">
              <h4>Its answer</h4>
              <MarkdownContent className="agent-detail-markdown">{stage1Text}</MarkdownContent>
            </section>
          ) : (
            <p className="agent-detail-empty">This model has not produced an answer for this run.</p>
          )}

          {rankingRow && (
            <section className="agent-detail-section">
              <h4>How {name} scored the council</h4>
              {parsed.length > 0 && (
                <ol className="agent-detail-ranking">
                  {parsed.map((label, index) => (
                    <li key={`${label}-${index}`}>
                      {labelToModel && labelToModel[label]
                        ? resolveModelLabel(labelToModel[label], modelMap)
                        : label}
                    </li>
                  ))}
                </ol>
              )}
              {rankingText && (
                <MarkdownContent className="agent-detail-markdown agent-detail-eval">
                  {rankingText}
                </MarkdownContent>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
