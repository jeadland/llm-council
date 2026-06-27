import { useState } from 'react';
import { AlertTriangle, Check, Crown } from 'lucide-react';
import { abbreviateModelName, formatModelLabel, providerMeta } from '../modelUtils';
import { deriveCouncilAgents } from '../councilState';
import AgentDetail from './AgentDetail';
import './CouncilTable.css';

const STATUS_TEXT = {
  pending: 'Waiting',
  thinking: 'Thinking',
  answered: 'Answered',
  rating: 'Rating',
  ranked: 'Ranked',
  winner: 'Winner',
  failed: 'No reply',
};

function AgentCard({ agent, modelMap, onSelect }) {
  const meta = providerMeta(agent.model);
  const name = abbreviateModelName(agent.model, modelMap) || formatModelLabel(agent.model);
  const fullName = formatModelLabel(agent.model);
  const interactive = agent.answered || agent.ranked;
  const isBusy = agent.state === 'thinking' || agent.state === 'rating';

  const statusText =
    agent.state === 'ranked' && agent.rank ? `#${agent.rank}` : STATUS_TEXT[agent.state];

  return (
    <button
      type="button"
      className={`agent-card agent-card--${agent.state}${interactive ? '' : ' agent-card--static'}`}
      onClick={interactive ? () => onSelect(agent) : undefined}
      disabled={!interactive}
      title={interactive ? `${fullName} — view detail` : fullName}
      aria-label={`${fullName}: ${STATUS_TEXT[agent.state]}`}
    >
      <span className="agent-avatar" style={{ '--agent-color': meta.color }} aria-hidden="true">
        {meta.glyph}
        {agent.state === 'winner' && (
          <span className="agent-avatar-crown" aria-hidden="true">
            <Crown size={11} />
          </span>
        )}
      </span>

      <span className="agent-card-body">
        <span className="agent-name">{name}</span>
        <span className={`agent-status agent-status--${agent.state}`}>
          {isBusy && <span className="agent-pulse" aria-hidden="true" />}
          {agent.state === 'answered' && <Check size={12} aria-hidden="true" />}
          {agent.state === 'winner' && <Crown size={12} aria-hidden="true" />}
          {agent.state === 'failed' && <AlertTriangle size={12} aria-hidden="true" />}
          <span>{statusText}</span>
        </span>
      </span>
    </button>
  );
}

export default function CouncilTable({ msg, modelMap, fallbackModels = [] }) {
  const [selectedModel, setSelectedModel] = useState(null);
  const agents = deriveCouncilAgents(msg, fallbackModels);

  if (agents.length === 0) return null;

  const labelToModel = msg.metadata?.label_to_model || null;
  const selectedAgent = agents.find((agent) => agent.model === selectedModel) || null;

  const answeredCount = agents.filter((a) => a.answered).length;
  const rankedCount = agents.filter((a) => a.ranked).length;
  const phase = msg.loading?.stage1
    ? `Drafting answers · ${answeredCount}/${agents.length}`
    : msg.loading?.stage2
      ? `Peer scoring · ${rankedCount}/${agents.length}`
      : msg.loading?.stage3
        ? 'Synthesizing verdict…'
        : 'Council complete';

  return (
    <div className="council-table">
      <div className="council-table-head">
        <span className="council-table-title">The Council</span>
        <span className="council-table-phase">{phase}</span>
      </div>

      <div className="council-strip" role="list">
        {agents.map((agent) => (
          <div role="listitem" key={agent.model}>
            <AgentCard
              agent={agent}
              modelMap={modelMap}
              onSelect={(a) => setSelectedModel(a.model)}
            />
          </div>
        ))}
      </div>

      {selectedAgent && (
        <AgentDetail
          agent={selectedAgent}
          labelToModel={labelToModel}
          modelMap={modelMap}
          onClose={() => setSelectedModel(null)}
        />
      )}
    </div>
  );
}
