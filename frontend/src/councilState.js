// Derives per-model "agent" state for the Council Table from an assistant message.
//
// An assistant message carries: stage1 (array, may be partial while streaming),
// stage2 (rankings array), metadata (stage1_execution, stage2_execution,
// aggregate_rankings), and loading flags. From these we compute each model's
// position in its journey: pending -> thinking -> answered -> rating -> ranked -> winner
// (or failed).

export const AGENT_STATES = [
  'pending',
  'thinking',
  'answered',
  'rating',
  'ranked',
  'winner',
  'failed',
];

export function deriveCouncilAgents(msg, fallbackModels = []) {
  if (!msg) return [];
  const meta = msg.metadata || {};
  const stage1Exec = meta.stage1_execution || null;
  const stage2Exec = meta.stage2_execution || null;
  const aggregate = Array.isArray(meta.aggregate_rankings) ? meta.aggregate_rankings : null;
  const stage1Data = Array.isArray(msg.stage1) ? msg.stage1 : [];
  const stage2Data = Array.isArray(msg.stage2) ? msg.stage2 : [];
  const loading = msg.loading || {};

  const models =
    (stage1Exec?.attempted_models?.length && stage1Exec.attempted_models) ||
    (stage2Exec?.attempted_models?.length && stage2Exec.attempted_models) ||
    (stage1Data.length && stage1Data.map((row) => row.model)) ||
    fallbackModels ||
    [];

  const stage1ByModel = new Map(stage1Data.map((row) => [row.model, row]));
  const stage2ByModel = new Map(stage2Data.map((row) => [row.model, row]));
  const aggByModel = new Map(
    (aggregate || []).map((entry, index) => [entry.model, { rank: index + 1, ...entry }]),
  );
  const stage1Failed = new Set(stage1Exec?.failed_models || []);
  const stage2Failed = new Set(stage2Exec?.failed_models || []);
  const winnerModel = aggregate?.[0]?.model || null;
  const stage2Settled = !loading.stage2 && (stage2Data.length > 0 || !!msg.stage3);

  return models.map((model) => {
    const stage1Row = stage1ByModel.get(model) || null;
    const rankingRow = stage2ByModel.get(model) || null;
    const agg = aggByModel.get(model) || null;
    const answered = !!stage1Row;
    const ranked = !!rankingRow;

    let state;
    if (stage1Failed.has(model) && !answered) {
      state = 'failed';
    } else if (stage2Failed.has(model) && !ranked) {
      state = 'failed';
    } else if (ranked && winnerModel === model && stage2Settled) {
      state = 'winner';
    } else if (ranked) {
      state = 'ranked';
    } else if (loading.stage2 && answered) {
      state = 'rating';
    } else if (answered) {
      state = 'answered';
    } else if (loading.stage1) {
      state = 'thinking';
    } else {
      state = 'pending';
    }

    return {
      model,
      state,
      answered,
      ranked,
      isWinner: state === 'winner',
      stage1Row,
      rankingRow,
      rank: agg?.rank ?? null,
      averageRank: typeof agg?.average_rank === 'number' ? agg.average_rank : null,
      rankingsCount: agg?.rankings_count ?? null,
    };
  });
}

export function councilWinner(agents = []) {
  return agents.find((agent) => agent.isWinner) || null;
}

/** True once peer scoring begins or a composite leaderboard exists. */
export function isCouncilRaceActive(msg, agents = []) {
  const loading = msg?.loading || {};
  const aggregate = msg?.metadata?.aggregate_rankings;
  if (loading.stage2) return agents.some((a) => a.answered);
  return Array.isArray(aggregate) && aggregate.length > 0;
}

/**
 * Sort agents for the "horse race" leaderboard: best composite rank leftmost
 * (finish line on the left). Models still scoring trail at the back.
 */
export function sortCouncilAgentsByRace(agents) {
  const indexed = agents.map((agent, councilIndex) => ({ agent, councilIndex }));

  indexed.sort((a, b) => {
    const agentA = a.agent;
    const agentB = b.agent;

    if (agentA.state === 'failed' && agentB.state !== 'failed') return 1;
    if (agentB.state === 'failed' && agentA.state !== 'failed') return -1;

    if (agentA.rank != null && agentB.rank != null) return agentA.rank - agentB.rank;
    if (agentA.rank != null) return -1;
    if (agentB.rank != null) return 1;

    // No composite rank yet — reviewers still scoring trail responders waiting
    if (agentA.state === 'rating' && agentB.state !== 'rating') return 1;
    if (agentB.state === 'rating' && agentA.state !== 'rating') return -1;

    return a.councilIndex - b.councilIndex;
  });

  return indexed.map(({ agent }) => agent);
}

export function displayCouncilAgents(msg, agents) {
  if (!isCouncilRaceActive(msg, agents)) return agents;
  return sortCouncilAgentsByRace(agents);
}
