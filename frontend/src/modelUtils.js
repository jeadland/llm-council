export function shortModelName(modelId) {
  return modelId?.split('/').pop() || modelId || '';
}

export function displayModelName(modelId, modelMap) {
  const model = modelMap?.get(modelId);
  return model?.name || shortModelName(modelId);
}

export function formatCurationText(value, fallback = '') {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    return value.map((item) => formatCurationText(item)).filter(Boolean).join('; ') || fallback;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return fallback;
  }
}

export function formatCurationList(value) {
  if (value === null || value === undefined || value === '') return [];
  const values = Array.isArray(value) ? value : [value];
  return values.map((item) => formatCurationText(item)).filter(Boolean);
}

export function formatCurationCost(value) {
  if (value === null || value === undefined || value === '') return null;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return null;
  return `$${numericValue.toFixed(4)}`;
}

export function abbreviateModelName(modelId, modelMap) {
  const label = displayModelName(modelId, modelMap)
    .replace(/^.*?:\s*/, '')
    .replace(/\s*\([^)]*\)\s*/g, ' ')
    .trim();
  const normalized = label.toLowerCase();

  if (!label) return '';

  const version = label.match(/\b(\d+(?:\.\d+)*)\b/);
  const versionLabel = version?.[1] || '';

  if (normalized.includes('gpt')) {
    return versionLabel ? `GPT-${versionLabel}` : 'GPT';
  }
  if (normalized.includes('gemini')) {
    return versionLabel ? `Gemini ${versionLabel}` : 'Gemini';
  }
  if (normalized.includes('claude')) {
    if (normalized.includes('sonnet')) {
      return versionLabel ? `Sonnet ${versionLabel}` : 'Sonnet';
    }
    if (normalized.includes('opus')) {
      return versionLabel ? `Opus ${versionLabel}` : 'Opus';
    }
    if (normalized.includes('haiku')) {
      return versionLabel ? `Haiku ${versionLabel}` : 'Haiku';
    }
    return 'Claude';
  }
  if (normalized.includes('grok')) {
    return versionLabel ? `Grok ${versionLabel}` : 'Grok';
  }
  if (normalized.includes('deepseek')) {
    return 'DeepSeek';
  }
  if (normalized.includes('llama')) {
    return versionLabel ? `Llama ${versionLabel}` : 'Llama';
  }
  if (normalized.includes('mistral')) {
    return 'Mistral';
  }
  if (normalized.includes('qwen')) {
    return 'Qwen';
  }

  const fallback = shortModelName(modelId) || label;
  return fallback
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .slice(0, 18)
    .trim();
}

export function sameModelSet(left = [], right = []) {
  const leftSet = new Set(left);
  const rightSet = new Set(right);
  if (leftSet.size !== rightSet.size) return false;
  return [...leftSet].every((modelId) => rightSet.has(modelId));
}

function chairmanMatches(expected, selected) {
  return !expected || expected === selected;
}

export function resolveActiveCouncil(settings, presets = []) {
  const activeId = settings?.active_model_group_id || '';
  const selected = settings?.council_models || [];
  const chairman = settings?.chairman_model || '';
  const custom = settings?.custom_model_groups?.find((group) => group.id === activeId);

  if (custom) {
    const exact = sameModelSet(custom.models || [], selected) && chairmanMatches(custom.chairman_model, chairman);
    return {
      name: custom.name,
      badge: exact ? 'Custom' : 'Review',
      custom,
      selectionMatches: exact,
      source: 'custom',
    };
  }

  const activePreset = presets?.find((item) => item.id === activeId);
  if (activePreset) {
    const exact = sameModelSet(activePreset.models || [], selected) && chairmanMatches(activePreset.chairman_model, chairman);
    return {
      name: activePreset.name,
      badge: exact ? (activePreset.badge || 'Curated') : 'Review',
      preset: activePreset,
      selectionMatches: exact,
      selectionMatchesPreset: exact,
      source: 'preset',
    };
  }

  const matched = presets?.find((preset) => (
    sameModelSet(preset.models || [], selected) && chairmanMatches(preset.chairman_model, chairman)
  ));
  if (matched) {
    return {
      name: matched.name,
      badge: matched.badge || 'Curated',
      preset: matched,
      selectionMatches: true,
      selectionMatchesPreset: true,
      source: 'preset',
    };
  }

  return {
    name: 'Custom Council',
    badge: 'Custom',
    selectionMatches: true,
    source: 'manual',
  };
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
