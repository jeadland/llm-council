const NICE_MODEL_NAMES = {
  'anthropic/claude-opus-4.6': 'Opus 4.6',
  'anthropic/claude-sonnet-4.6': 'Sonnet 4.6',
  'anthropic/claude-haiku-4.5': 'Haiku 4.5',
  'google/gemini-3.1-pro-preview': 'Gemini 3.1 Pro Preview',
  'google/gemini-2.5-pro': 'Gemini 2.5 Pro',
  'x-ai/grok-4': 'Grok 4',
  'x-ai/grok-4.20': 'Grok 4.20',
  'x-ai/grok-4.3': 'Grok 4.3',
  'x-ai/grok-4.1-fast': 'Grok 4.1 Fast',
  'openai/gpt-5.2': 'GPT-5.2',
  'openai/gpt-5.2-chat': 'GPT-5.2 Chat',
  'openai/gpt-5.2-pro': 'GPT-5.2 Pro',
  'openai/gpt-5.4': 'GPT-5.4',
};

// Shared friendly label used across Stage 1/2/3 and the council table.
export function formatModelLabel(model) {
  if (!model) return 'Unknown';
  const raw = model.startsWith('openrouter/') ? model.replace('openrouter/', '') : model;
  return NICE_MODEL_NAMES[raw] || raw;
}

// Compact, consistent label for tabs, headers, and race cards.
export function resolveModelLabel(modelId, modelMap) {
  return abbreviateModelName(modelId, modelMap) || formatModelLabel(modelId);
}

const PROVIDER_LOGO_SLUG = {
  anthropic: 'anthropic',
  openai: 'openai',
  google: 'google',
  'x-ai': 'x-ai',
  xai: 'x-ai',
  deepseek: 'deepseek',
  meta: 'meta',
  'meta-llama': 'meta',
  mistral: 'mistral',
  mistralai: 'mistral',
  qwen: 'qwen',
  cohere: 'cohere',
  perplexity: 'perplexity',
};

const PROVIDER_META = {
  anthropic: { label: 'Anthropic', color: '#d97757', glyph: 'A' },
  openai: { label: 'OpenAI', color: '#10a37f', glyph: 'O' },
  google: { label: 'Google', color: '#4285f4', glyph: 'G' },
  'x-ai': { label: 'xAI', color: '#1f2937', glyph: 'X' },
  xai: { label: 'xAI', color: '#1f2937', glyph: 'X' },
  deepseek: { label: 'DeepSeek', color: '#4d6bfe', glyph: 'D' },
  'meta-llama': { label: 'Meta', color: '#0866ff', glyph: 'M' },
  meta: { label: 'Meta', color: '#0866ff', glyph: 'M' },
  mistralai: { label: 'Mistral', color: '#fa5310', glyph: 'M' },
  mistral: { label: 'Mistral', color: '#fa5310', glyph: 'M' },
  qwen: { label: 'Qwen', color: '#6f3df5', glyph: 'Q' },
  cohere: { label: 'Cohere', color: '#39594d', glyph: 'C' },
  perplexity: { label: 'Perplexity', color: '#20808d', glyph: 'P' },
};

export function providerLogoSrc(provider) {
  const slug = PROVIDER_LOGO_SLUG[(provider || '').toLowerCase()];
  if (!slug) return null;
  return `${import.meta.env.BASE_URL}images/providers/${slug}.svg`;
}

export function hasProviderLogo(provider) {
  return Boolean(PROVIDER_LOGO_SLUG[(provider || '').toLowerCase()]);
}

// Provider identity for an avatar: brand color + glyph derived from the model id prefix.
export function providerMeta(modelId) {
  const raw = (modelId || '').replace(/^openrouter\//, '');
  const provider = (raw.split('/')[0] || '').toLowerCase();
  const meta = PROVIDER_META[provider];
  if (meta) return { provider, ...meta };
  return {
    provider,
    label: provider || 'Model',
    color: '#64748b',
    glyph: (provider[0] || '?').toUpperCase(),
  };
}

export function shortModelName(modelId) {
  return modelId?.split('/').pop() || modelId || '';
}

export function displayModelName(modelId, modelMap) {
  const model = modelMap?.get(modelId);
  return model?.name || shortModelName(modelId);
}

function pickCurationField(obj, keys) {
  for (const key of keys) {
    const value = obj[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return '';
}

function formatCurationStructuredValue(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }

  const risk = pickCurationField(value, ['risk', 'issue', 'warning', 'note']);
  const impact = pickCurationField(value, ['impact', 'effect', 'consequence']);
  if (risk && impact) {
    return `${risk} — ${impact}`;
  }
  if (risk) {
    return risk;
  }

  const summary = pickCurationField(value, ['summary', 'text', 'message', 'description']);
  if (summary) {
    return summary;
  }

  return null;
}

function tryParseCurationJsonString(value) {
  const trimmed = value.trim();
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) {
    return null;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

export function formatCurationText(value, fallback = '') {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'string') {
    const parsed = tryParseCurationJsonString(value);
    if (parsed) {
      const formatted = formatCurationStructuredValue(parsed);
      if (formatted) return formatted;
    }
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    return value.map((item) => formatCurationText(item)).filter(Boolean).join('; ') || fallback;
  }
  const formatted = formatCurationStructuredValue(value);
  if (formatted) return formatted;
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
  if (!Number.isFinite(numericValue) || numericValue < 0) return null;
  return `$${numericValue.toFixed(4)}`;
}

export function formatCurationDate(value) {
  if (!value) return 'Unknown date';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown date';
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function formatCurationStatusLabel(status, { approved = false } = {}) {
  if (approved) return 'Approved';
  switch (status) {
    case 'ready':
      return 'Ready for review';
    case 'ready_with_warnings':
      return 'Ready with warnings';
    case 'skipped_cost_cap':
      return 'Skipped (cost cap)';
    default:
      return status ? String(status).replace(/_/g, ' ') : 'Unknown';
  }
}

function modelListsEqual(a, b) {
  const left = [...(a || [])].sort();
  const right = [...(b || [])].sort();
  if (left.length !== right.length) return false;
  return left.every((id, index) => id === right[index]);
}

export function diffCurationPresets(currentPresets, proposedPresets) {
  const currentById = new Map((currentPresets || []).map((preset) => [preset.id, preset]));
  const proposedById = new Map((proposedPresets || []).map((preset) => [preset.id, preset]));
  const ids = [...new Set([...currentById.keys(), ...proposedById.keys()])];

  return ids
    .map((id) => {
      const current = currentById.get(id);
      const proposed = proposedById.get(id);
      if (!proposed) return null;

      const modelsChanged = !modelListsEqual(current?.models, proposed?.models);
      const chairmanChanged = (current?.chairman_model || '') !== (proposed?.chairman_model || '');
      const currentModels = new Set(current?.models || []);
      const proposedModels = proposed?.models || [];
      const removedModels = (current?.models || []).filter((modelId) => !proposedModels.includes(modelId));
      const addedModels = proposedModels.filter((modelId) => !currentModels.has(modelId));

      return {
        id,
        name: proposed.name || current?.name || id,
        current,
        proposed,
        changed: !current || modelsChanged || chairmanChanged,
        modelsChanged,
        chairmanChanged,
        addedModels,
        removedModels,
        missingModels: proposed.missing || [],
      };
    })
    .filter(Boolean);
}

export function buildCurationSummary({ draft, presetDiffs }) {
  if (!draft) return '';
  const createdAt = formatCurationDate(draft.created_at);
  if (draft.approved_at) {
    return `Approved preset updates from ${formatCurationDate(draft.approved_at)} are live.`;
  }
  const changedCount = (presetDiffs || []).filter((diff) => diff.changed).length;
  if (changedCount === 0) {
    return `Draft from ${createdAt}: curator checked the catalog and recommends no preset lineup changes.`;
  }
  return `Draft from ${createdAt}: recommends updates to ${changedCount} curated preset${changedCount === 1 ? '' : 's'} based on the current OpenRouter catalog.`;
}

export function formatCurationWarnings(risks) {
  const seen = new Set();
  const warnings = [];

  for (const raw of formatCurationList(risks)) {
    const warning = humanizeCurationWarning(raw);
    if (warning && !seen.has(warning)) {
      seen.add(warning);
      warnings.push(warning);
    }
  }

  return warnings;
}

function humanizeCurationWarning(text) {
  const normalized = text.trim();
  if (!normalized) return null;

  const impact = normalized.includes(' — ')
    ? normalized.split(' — ').slice(1).join(' — ').trim()
    : '';
  const source = normalized.includes(' — ')
    ? normalized.split(' — ')[0].trim()
    : normalized;

  if (/catalog_candidates|non-catalog ids|latest-alias|byok presets?/i.test(source)) {
    return impact || 'Some proposed models may not match the live OpenRouter catalog.';
  }
  if (/open-source|open-weights/i.test(normalized)) {
    return impact || 'Open-source labels are approximate and may not reflect self-hosting options.';
  }
  if (/leaderboard|catalog can change|provider catalog/i.test(normalized)) {
    return 'Model availability can change after this draft was generated.';
  }
  if (/cost|surcharge|pricing/i.test(normalized)) {
    return impact || 'Cost estimates may not include all provider surcharges.';
  }
  if (/fail at runtime|unavailable models/i.test(normalized)) {
    return impact || 'Some proposed models may be unavailable until the draft is revised.';
  }
  if (/[{[\]"]/.test(normalized)) {
    return null;
  }
  if (normalized.length > 160) {
    return impact || null;
  }
  return impact || normalized;
}

export function abbreviateModelName(modelId, modelMap) {
  const label = displayModelName(modelId, modelMap)
    .replace(/^.*?:\s*/, '')
    .replace(/\s*\([^)]*\)\s*/g, ' ')
    .trim();
  const normalized = label.toLowerCase();

  if (!label) return '';

  const version = label.match(/\b(\d+(?:\.\d+)*)\b/);
  const versionSuffix = label.match(/v(\d+(?:\.\d+)*)/i);
  const versionLabel = version?.[1] || versionSuffix?.[1] || '';

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
  if (normalized.includes('glm')) {
    return versionLabel ? `GLM ${versionLabel}` : 'GLM';
  }
  if (normalized.includes('deepseek')) {
    return versionLabel ? `DeepSeek ${versionLabel}` : 'DeepSeek';
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

const MANAGED_PRESET_PROFILE_SLUGS = {
  'efficient-daily': 'quick',
  'premium-balanced': 'balanced',
  'ultra-premium-frontier': 'ultra',
};

export function resolveManagedProfileSlug(settings, presets = [], councilProfiles = []) {
  const activeId = settings?.active_model_group_id || '';
  const selected = settings?.council_models || [];
  const chairman = settings?.chairman_model || '';

  const matchingProfiles = (councilProfiles || []).filter((profile) => (
    profile.enabled
    && sameModelSet(profile.models || [], selected)
    && chairmanMatches(profile.chairman_model, chairman)
  ));
  if (matchingProfiles.length > 0) {
    return matchingProfiles[matchingProfiles.length - 1].slug;
  }

  const activePreset = presets?.find((item) => item.id === activeId);
  if (activePreset?.id && MANAGED_PRESET_PROFILE_SLUGS[activePreset.id]) {
    const exact = sameModelSet(activePreset.models || [], selected)
      && chairmanMatches(activePreset.chairman_model, chairman);
    if (exact) {
      return MANAGED_PRESET_PROFILE_SLUGS[activePreset.id];
    }
  }

  const matchedPreset = presets?.find((preset) => (
    sameModelSet(preset.models || [], selected) && chairmanMatches(preset.chairman_model, chairman)
  ));
  if (matchedPreset?.id && MANAGED_PRESET_PROFILE_SLUGS[matchedPreset.id]) {
    return MANAGED_PRESET_PROFILE_SLUGS[matchedPreset.id];
  }

  return null;
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
