import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { AlertTriangle, ArrowDown, ArrowUp, Check, ChevronRight, Crown } from 'lucide-react';
import { formatModelLabel, resolveModelLabel } from '../modelUtils';
import ProviderAvatar from './ProviderAvatar';
import {
  deriveCouncilAgents,
  displayCouncilAgents,
  isCouncilRaceActive,
} from '../councilState';
import AgentDetail from './AgentDetail';
import './CouncilTable.css';

const STATUS_TEXT = {
  pending: 'Waiting',
  thinking: 'Thinking',
  answered: 'Answered',
  rating: 'Scoring',
  ranked: 'Ranked',
  winner: 'Winner',
  failed: 'No reply',
};

function formatRaceStatus(agent, raceActive) {
  if (raceActive && agent.rank != null && typeof agent.averageRank === 'number') {
    const votes =
      agent.rankingsCount != null
        ? ` · ${agent.rankingsCount}v`
        : '';
    return `#${agent.rank} · ${agent.averageRank.toFixed(2)} avg${votes}`;
  }
  if (agent.state === 'ranked' && agent.rank) return `#${agent.rank}`;
  return STATUS_TEXT[agent.state];
}

function AgentCard({ agent, modelMap, onSelect, raceActive, rankShift }) {
  const name = resolveModelLabel(agent.model, modelMap);
  const fullName = formatModelLabel(agent.model);
  const interactive = agent.answered || agent.ranked;
  const isBusy = agent.state === 'thinking' || agent.state === 'rating';
  const statusText = formatRaceStatus(agent, raceActive);

  return (
    <button
      type="button"
      className={`agent-card agent-card--${agent.state}${interactive ? '' : ' agent-card--static'}${raceActive && agent.rank === 1 ? ' agent-card--leader' : ''}${rankShift === 'up' ? ' agent-card--surged-up' : ''}${rankShift === 'down' ? ' agent-card--surged-down' : ''}`}
      onClick={interactive ? () => onSelect(agent) : undefined}
      disabled={!interactive}
      title={interactive ? `${fullName} — view detail` : fullName}
      aria-label={`${fullName}: ${statusText}`}
    >
      {raceActive && agent.rank != null && (
        <span className="agent-lane-badge" aria-hidden="true">
          {agent.rank}
        </span>
      )}

      <ProviderAvatar className="agent-avatar" modelId={agent.model} aria-hidden="true">
        {agent.state === 'winner' && (
          <span className="agent-avatar-crown" aria-hidden="true">
            <Crown size={11} />
          </span>
        )}
      </ProviderAvatar>

      <span className="agent-card-body">
        <span className="agent-name">{name}</span>
        <span className={`agent-status agent-status--${agent.state}`}>
          {isBusy && <span className="agent-pulse" aria-hidden="true" />}
          {agent.state === 'answered' && !raceActive && <Check size={12} aria-hidden="true" />}
          {agent.state === 'winner' && <Crown size={12} aria-hidden="true" />}
          {agent.state === 'failed' && <AlertTriangle size={12} aria-hidden="true" />}
          {rankShift === 'up' && <ArrowUp size={12} className="agent-shift-icon agent-shift-icon--up" aria-hidden="true" />}
          {rankShift === 'down' && <ArrowDown size={12} className="agent-shift-icon agent-shift-icon--down" aria-hidden="true" />}
          <span>{statusText}</span>
        </span>
      </span>
    </button>
  );
}

function useFlipReorder(items, stripRef) {
  const positionsRef = useRef(new Map());

  useLayoutEffect(() => {
    const strip = stripRef.current;
    if (!strip) return;

    strip.querySelectorAll('[data-race-model]').forEach((el) => {
      const model = el.dataset.raceModel;
      const prev = positionsRef.current.get(model);
      const rect = el.getBoundingClientRect();

      if (prev) {
        const dx = prev.left - rect.left;
        const dy = prev.top - rect.top;
        if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
          el.style.transform = `translate(${dx}px, ${dy}px)`;
          el.style.transition = 'transform 0s';
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              el.style.transform = '';
              el.style.transition = 'transform 0.45s cubic-bezier(0.22, 1, 0.36, 1)';
            });
          });
        }
      }

      positionsRef.current.set(model, { left: rect.left, top: rect.top });
    });
  }, [items, stripRef]);
}

function usePrevious(value) {
  const ref = useRef(undefined);
  useLayoutEffect(() => {
    ref.current = value;
  }, [value]);
  // Previous render snapshot; safe to read for diffing poll updates.
  // eslint-disable-next-line react-hooks/refs
  return ref.current;
}

function useMobileLayout(maxWidth = 720) {
  const query = `(max-width: ${maxWidth}px)`;
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setIsMobile(media.matches);
    onChange();
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [query]);

  return isMobile;
}

function useRankShifts(agents, enabled) {
  const prevAgents = usePrevious(enabled ? agents : null);
  const shifts = {};

  if (enabled && Array.isArray(prevAgents)) {
    const prevByModel = new Map(prevAgents.map((agent) => [agent.model, agent.rank]));
    agents.forEach((agent) => {
      if (agent.rank == null) return;
      const prev = prevByModel.get(agent.model);
      if (prev != null && prev !== agent.rank) {
        shifts[agent.model] = agent.rank < prev ? 'up' : 'down';
      }
    });
  }

  return shifts;
}

export default function CouncilTable({ msg, modelMap, fallbackModels = [] }) {
  const [selectedModel, setSelectedModel] = useState(null);
  const [raceCollapsed, setRaceCollapsed] = useState(true);
  const stripRef = useRef(null);
  const isMobile = useMobileLayout();
  const rawAgents = deriveCouncilAgents(msg, fallbackModels);
  const raceActive = isCouncilRaceActive(msg, rawAgents);
  const agents = displayCouncilAgents(msg, rawAgents);
  const rankShifts = useRankShifts(agents, raceActive);
  const isLiveRace = Boolean(msg.loading?.stage2);
  const isCollapsibleRace = raceActive && !isLiveRace;
  const showRaceCollapsed = isMobile && isCollapsibleRace && raceCollapsed;

  useFlipReorder(agents, stripRef);

  if (agents.length === 0) return null;

  const labelToModel = msg.metadata?.label_to_model || null;
  const selectedAgent = agents.find((agent) => agent.model === selectedModel) || null;
  const stage2Exec = msg.metadata?.stage2_execution || null;
  const completedVotes = Number(stage2Exec?.completed_rankings_count ?? 0);
  const expectedVotes = Number(stage2Exec?.expected_rankings_count ?? agents.length);

  const answeredCount = rawAgents.filter((a) => a.answered).length;
  const rankedCount = rawAgents.filter((a) => a.ranked).length;

  const isRaceComplete = raceActive && !msg.loading?.stage1 && !msg.loading?.stage2 && !msg.loading?.stage3;
  const raceTitle = 'Peer reviewed response rankings';

  const phase = msg.loading?.stage1
    ? `Drafting answers · ${answeredCount}/${agents.length}`
    : msg.loading?.stage2
      ? raceActive && completedVotes > 0
        ? `Leaderboard shifting · ${completedVotes}/${expectedVotes} votes in`
        : `Peer scoring · ${rankedCount}/${agents.length}`
      : msg.loading?.stage3
        ? 'Synthesizing verdict…'
        : raceActive
          ? null
          : 'Council complete';

  const leader = agents.find((agent) => agent.rank === 1);
  const raceSummary = leader
    ? `${resolveModelLabel(leader.model, modelMap)} · #${leader.rank}`
    : null;
  const phaseDisplay = showRaceCollapsed
    ? raceSummary
    : isRaceComplete
      ? null
      : phase;

  const raceBody = (
    <>
      {raceActive && (
        <div className="council-race-hint" aria-hidden="true">
          <span className="council-race-finish">Finish</span>
          <span className="council-race-track-line" />
        </div>
      )}

      <div
        className={`council-strip${raceActive ? ' council-strip--race' : ''}`}
        ref={stripRef}
        role="list"
      >
        {agents.map((agent) => (
          <div role="listitem" key={agent.model} data-race-model={agent.model} className="council-race-slot">
            <AgentCard
              agent={agent}
              modelMap={modelMap}
              onSelect={(a) => setSelectedModel(a.model)}
              raceActive={raceActive}
              rankShift={rankShifts[agent.model] || null}
            />
          </div>
        ))}
      </div>
    </>
  );

  return (
    <div
      className={`council-table${raceActive ? ' council-table--race' : ''}${showRaceCollapsed ? ' council-table--race-collapsed' : ''}`}
    >
      {isCollapsibleRace && isMobile ? (
        <button
          type="button"
          className="council-table-head council-table-head--toggle"
          aria-expanded={!raceCollapsed}
          onClick={() => setRaceCollapsed((value) => !value)}
        >
          <span className="council-table-head-main">
            <ChevronRight className="council-table-chevron" size={15} aria-hidden="true" />
            <span className="council-table-title">{raceTitle}</span>
          </span>
          {phaseDisplay && (
            <span className="council-table-phase">{phaseDisplay}</span>
          )}
        </button>
      ) : (
        <div className="council-table-head">
          <span className="council-table-title">
            {raceActive ? raceTitle : 'The Council'}
          </span>
          {phaseDisplay && (
            <span className="council-table-phase">{phaseDisplay}</span>
          )}
        </div>
      )}

      {!showRaceCollapsed && raceBody}

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
