export function shortModelName(modelId) {
  return modelId?.split('/').pop() || modelId || '';
}

export function displayModelName(modelId, modelMap) {
  const model = modelMap?.get(modelId);
  return model?.name || shortModelName(modelId);
}

export function formatContext(tokens) {
  if (!tokens) return 'Unknown context';
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(tokens % 1_000_000 === 0 ? 0 : 1)}M ctx`;
  if (tokens >= 1_000) return `${Math.round(tokens / 1_000)}k ctx`;
  return `${tokens} ctx`;
}

export function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  if (value < 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(2)}`;
}

function modelCost(model, inputTokens, outputTokens) {
  const prompt = model?.pricing?.prompt_per_million;
  const completion = model?.pricing?.completion_per_million;
  if (prompt === null || prompt === undefined || completion === null || completion === undefined) return null;
  return (prompt * inputTokens / 1_000_000) + (completion * outputTokens / 1_000_000);
}

export function estimateCouncilCosts(modelIds, chairmanModel, modelMap) {
  const models = (modelIds || []).map((id) => modelMap?.get(id)).filter(Boolean);
  const chairman = modelMap?.get(chairmanModel);
  if (!models.length || !chairman) return null;

  const scenarios = {
    normal: {
      inputTokens: 6000,
      stage1OutputTokens: 1200,
      stage2OutputTokens: 700,
      stage3OutputTokens: 1200,
    },
  };

  const scenario = scenarios.normal;
  const n = models.length;
  let total = 0;
  for (const model of models) {
    const stage1 = modelCost(model, scenario.inputTokens, scenario.stage1OutputTokens);
    const stage2 = modelCost(
      model,
      scenario.inputTokens + (scenario.stage1OutputTokens * n),
      scenario.stage2OutputTokens,
    );
    if (stage1 === null || stage2 === null) return null;
    total += stage1 + stage2;
  }

  const stage3 = modelCost(
    chairman,
    scenario.inputTokens + (scenario.stage1OutputTokens * n) + (scenario.stage2OutputTokens * n),
    scenario.stage3OutputTokens,
  );
  if (stage3 === null) return null;
  total += stage3;

  return {
    low: total * 0.75,
    high: total * 1.45,
    display: `${formatMoney(total * 0.75)} - ${formatMoney(total * 1.45)}`,
  };
}

export function presetNormalCost(preset) {
  return preset?.estimated_costs?.scenarios?.normal?.display || null;
}

export function makeCustomGroupId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `custom-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}
