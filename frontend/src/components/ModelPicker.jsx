import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronRight, CopyPlus, Loader2, Search, Sparkles, X } from 'lucide-react';
import { api } from '../api';
import {
  displayModelName,
  estimateCouncilCosts,
  formatContext,
  formatCurationCost,
  formatCurationList,
  formatCurationText,
  formatMoney,
  makeCustomGroupId,
  presetNormalCost,
  shortModelName,
} from '../modelUtils';
import './ModelPicker.css';

const CAPABILITY_FILTERS = [
  'Recommended',
  'Frontier',
  'Chairman',
  'Tools',
  'Reasoning',
  'Long context',
  'Free',
];

function ModelPill({ modelId, modelMap, muted = false }) {
  const model = modelMap.get(modelId);
  return (
    <span className={`model-picker-pill${muted ? ' muted' : ''}`}>
      {model?.name?.replace(/^.*?:\s*/, '') || shortModelName(modelId)}
      {!model && <span className="model-picker-pill-warning">stale</span>}
    </span>
  );
}

function CurationPresetPreview({ preset, modelMap }) {
  const models = preset.models || [];

  return (
    <div className="curation-preset-card">
      <strong>{preset.name}</strong>
      <span>{models.length || 0} models · Chair {shortModelName(preset.chairman_model)}</span>
      {models.length > 0 && (
        <div className="curation-preset-models" aria-label={`${preset.name} model lineup`}>
          {models.map((modelId) => (
            <ModelPill key={modelId} modelId={modelId} modelMap={modelMap} />
          ))}
        </div>
      )}
    </div>
  );
}

function formatModelPricing(model) {
  const prompt = model?.pricing?.prompt_per_million;
  const completion = model?.pricing?.completion_per_million;
  if (prompt === null || prompt === undefined || completion === null || completion === undefined) {
    return 'Pricing unavailable';
  }
  return `${formatMoney(prompt)}/M in · ${formatMoney(completion)}/M out`;
}

function PresetRow({ preset, selected, modelMap, onSelect, onCustomize }) {
  const normalCost = presetNormalCost(preset) || 'Pricing unavailable';
  return (
    <section className={`preset-row${selected ? ' selected' : ''}`}>
      <button type="button" className="preset-radio" onClick={() => onSelect(preset)} aria-label={`Select ${preset.name}`}>
        {selected && <Check size={14} />}
      </button>
      <div className="preset-row-main">
        <div className="preset-row-title">
          <h3>{preset.name}</h3>
          {preset.badge && <span className="preset-badge">{preset.badge}</span>}
        </div>
        <p>{preset.summary || preset.best_for}</p>
        <div className="preset-explainer-grid">
          <div>
            <span>Best for</span>
            <strong>{preset.best_for}</strong>
          </div>
          <div>
            <span>Tradeoff</span>
            <strong>{preset.tradeoff || 'Balanced against cost and speed.'}</strong>
          </div>
          <div>
            <span>Recommended chairman</span>
            <strong className="chairman-text">
              <Sparkles size={16} />
              {displayModelName(preset.chairman_model, modelMap).replace(/^.*?:\s*/, '')}
            </strong>
          </div>
          <div>
            <span>Est. normal question</span>
            <strong>{normalCost}</strong>
          </div>
        </div>
        <div className="preset-model-lineup">
          {(preset.models || []).map((modelId) => (
            <ModelPill key={modelId} modelId={modelId} modelMap={modelMap} />
          ))}
          {(preset.missing || []).map((modelId) => (
            <ModelPill key={modelId} modelId={modelId} modelMap={modelMap} muted />
          ))}
        </div>
      </div>
      <div className="preset-row-actions">
        <button type="button" className="model-picker-secondary" onClick={() => onCustomize(preset)}>
          <CopyPlus size={15} />
          Customize copy
        </button>
        <button type="button" className="preset-row-open" onClick={() => onSelect(preset)} aria-label={`Use ${preset.name}`}>
          <ChevronRight size={18} />
        </button>
      </div>
    </section>
  );
}

function ModelRow({ model, selected, chairman, onToggle, onChairman }) {
  const isChairman = chairman === model.id;
  return (
    <div className={`model-row${selected ? ' selected' : ''}${isChairman ? ' chairman' : ''}`}>
      <button
        type="button"
        className="model-row-main"
        onClick={() => onToggle(model.id)}
        aria-pressed={selected}
      >
        <span className="model-row-check" aria-hidden="true">{selected ? <Check size={14} /> : null}</span>
        <span className="model-row-text">
          <span className="model-row-name">{model.name}</span>
          <span className="model-row-meta">
            <span className="model-row-id">{model.id}</span>
            <span className="model-row-price">{formatModelPricing(model)}</span>
          </span>
          <span className="model-row-tags">
            <span>{model.provider}</span>
            <span>{model.price_tier}</span>
            <span>{formatContext(model.context_length)}</span>
            {(model.recommendation_tags || []).slice(0, 3).map((tag) => (
              <span key={tag}>{tag}</span>
            ))}
          </span>
        </span>
      </button>
      <button
        type="button"
        className="model-row-chairman"
        onClick={() => onChairman(model.id)}
        disabled={!selected}
        aria-pressed={isChairman}
        title={selected ? 'Use as chairman' : 'Add to council before selecting as chairman'}
      >
        {isChairman ? 'Chairman' : 'Set chair'}
      </button>
    </div>
  );
}

export default function ModelPicker({
  open,
  selectedCouncil,
  selectedChairman,
  activeGroupId,
  customGroups = [],
  onApply,
  onSaveCustomGroup,
  onCurationApproved,
  onOpenIntegrations,
  onClose,
}) {
  const [status, setStatus] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [presets, setPresets] = useState([]);
  const [providers, setProviders] = useState([]);
  const [curationDraft, setCurationDraft] = useState(null);
  const [curationPendingReview, setCurationPendingReview] = useState(false);
  const [curationState, setCurationState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [curationBusy, setCurationBusy] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('curated');
  const [localCouncil, setLocalCouncil] = useState(selectedCouncil || []);
  const [localChairman, setLocalChairman] = useState(selectedChairman || '');
  const [localActiveGroupId, setLocalActiveGroupId] = useState(activeGroupId || '');
  const [search, setSearch] = useState('');
  const [provider, setProvider] = useState('');
  const [priceTier, setPriceTier] = useState('');
  const [capability, setCapability] = useState('');
  const [minContext, setMinContext] = useState('');

  useEffect(() => {
    if (!open) return;
    setLocalCouncil(selectedCouncil || []);
    setLocalChairman(selectedChairman || '');
    setLocalActiveGroupId(activeGroupId || '');
    setError('');
  }, [open, selectedCouncil, selectedChairman, activeGroupId]);

  useEffect(() => {
    if (!open) return;
    let canceled = false;
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const [statusData, catalogData, curationData] = await Promise.all([
          api.getModelStatus(),
          api.getModelCatalog(),
          api.getLatestModelCuration(),
        ]);
        if (canceled) return;
        setStatus(statusData);
        setCatalog(catalogData.models || []);
        setPresets(catalogData.presets || []);
        setProviders(catalogData.providers || []);
        setCurationDraft(curationData.draft || null);
        setCurationPendingReview(Boolean(curationData.pending_review));
        setCurationState(curationData.curation_state || null);
      } catch (e) {
        if (!canceled) setError(e.message || 'Failed to load model catalog.');
      } finally {
        if (!canceled) setLoading(false);
      }
    };
    load();
    return () => {
      canceled = true;
    };
  }, [open]);

  const modelMap = useMemo(() => new Map(catalog.map((model) => [model.id, model])), [catalog]);
  const normalEstimate = estimateCouncilCosts(localCouncil, localChairman, modelMap)?.display;
  const curationNotes = formatCurationText(
    curationDraft?.notes,
    'Review updated model evaluations and lineup suggestions.',
  );
  const curationRisks = formatCurationList(curationDraft?.risks);
  const curationCost = formatCurationCost(curationDraft?.estimated_llm_cost);

  const filteredModels = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const minContextValue = minContext ? Number(minContext) : 0;
    return catalog.filter((model) => {
      if (needle) {
        const haystack = [
          model.id,
          model.name,
          model.provider,
          model.description,
          ...(model.recommendation_tags || []),
        ].join(' ').toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      if (provider && model.provider !== provider) return false;
      if (priceTier && model.price_tier !== priceTier) return false;
      if (capability && !(model.recommendation_tags || []).includes(capability)) return false;
      if (minContextValue && (model.context_length || 0) < minContextValue) return false;
      return true;
    });
  }, [catalog, search, provider, priceTier, capability, minContext]);

  if (!open) return null;

  const toggleModel = (modelId) => {
    setLocalActiveGroupId('');
    setLocalCouncil((prev) => {
      if (prev.includes(modelId)) {
        const next = prev.filter((id) => id !== modelId);
        if (localChairman === modelId) setLocalChairman(next[0] || '');
        return next;
      }
      if (!localChairman) setLocalChairman(modelId);
      return [...prev, modelId];
    });
  };

  const selectPreset = (preset) => {
    setLocalCouncil(preset.models || []);
    setLocalChairman(preset.chairman_model || preset.models?.[0] || '');
    setLocalActiveGroupId(preset.id);
  };

  const selectCustom = (group) => {
    setLocalCouncil(group.models || []);
    setLocalChairman(group.chairman_model || group.models?.[0] || '');
    setLocalActiveGroupId(group.id);
  };

  const saveCustomCopy = async (sourcePreset = null) => {
    const defaultName = sourcePreset ? `${sourcePreset.name} Copy` : 'Custom Council';
    const name = window.prompt('Name this custom council', defaultName);
    if (!name?.trim()) return;
    const group = {
      id: makeCustomGroupId(),
      name: name.trim(),
      models: sourcePreset?.models || localCouncil,
      chairman_model: sourcePreset?.chairman_model || localChairman,
      source_preset_id: sourcePreset?.id || localActiveGroupId || null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    await onSaveCustomGroup?.(group);
    setLocalCouncil(group.models);
    setLocalChairman(group.chairman_model);
    setLocalActiveGroupId(group.id);
    setActiveTab('custom');
  };

  const runCuration = async () => {
    setCurationBusy(true);
    setError('');
    try {
      const data = await api.runModelCuration();
      setCurationDraft(data.draft);
      setCurationPendingReview(data.draft?.status === 'ready');
      setCurationState(data.curation_state || null);
      setActiveTab('review');
    } catch (e) {
      setError(e.message || 'Failed to run model curation.');
    } finally {
      setCurationBusy(false);
    }
  };

  const approveCuration = async () => {
    if (!curationDraft?.id) return;
    setCurationBusy(true);
    setError('');
    try {
      const data = await api.approveModelCuration(curationDraft.id);
      onCurationApproved?.(data.settings);
      const catalogData = await api.getModelCatalog();
      setPresets(catalogData.presets || []);
      setCurationDraft(data.draft || { ...curationDraft, approved_at: new Date().toISOString() });
      setCurationPendingReview(false);
    } catch (e) {
      setError(e.message || 'Failed to approve curation draft.');
    } finally {
      setCurationBusy(false);
    }
  };

  const apply = () => {
    if (localCouncil.length === 0 || !localChairman) return;
    onApply({
      council_models: localCouncil,
      chairman_model: localChairman,
      active_model_group_id: localActiveGroupId,
    });
    onClose();
  };

  return (
    <div className="model-picker-backdrop" role="presentation">
      <div className="model-picker" role="dialog" aria-modal="true" aria-labelledby="model-picker-title">
        <div className="model-picker-header">
          <div>
            <h2 id="model-picker-title">Choose or customize your council</h2>
            <p>Councils are curated groups of models. The chairman guides the discussion and synthesizes the final answer.</p>
          </div>
          <button type="button" className="model-picker-close" onClick={onClose} aria-label="Close model picker">
            <X size={20} />
          </button>
        </div>

        {!loading && status && !status.openrouter_key_configured && (
          <div className="model-picker-warning">
            <span>
              Add your OpenRouter key in API &amp; Integrations to run direct hosted councils when the local OpenClaw proxy is unavailable.
            </span>
            {onOpenIntegrations && (
              <button type="button" onClick={onOpenIntegrations}>
                Add key
              </button>
            )}
          </div>
        )}

        {error && <div className="model-picker-error">{error}</div>}

        <div className="model-picker-tabs" role="tablist" aria-label="Model picker sections">
          {[
            ['curated', 'Curated presets', 'Presets'],
            ['custom', 'Custom groups', 'Groups'],
            ['browse', 'Browse models', 'Browse'],
            ['review', 'Curation Review', 'Review'],
          ].map(([id, label, shortLabel]) => (
            <button
              key={id}
              type="button"
              className={activeTab === id ? 'active' : ''}
              onClick={() => setActiveTab(id)}
              role="tab"
              aria-selected={activeTab === id}
            >
              <span className="model-picker-tab-label model-picker-tab-label--long">{label}</span>
              <span className="model-picker-tab-label model-picker-tab-label--short">{shortLabel}</span>
              {id === 'review' && curationPendingReview && <span className="tab-count">1</span>}
            </button>
          ))}
        </div>

        <div className="model-picker-body">
          {loading && (
            <div className="model-picker-loading">
              <Loader2 className="spin" size={20} />
              <span>Loading OpenRouter catalog...</span>
            </div>
          )}

          {!loading && activeTab === 'curated' && (
            <div className="preset-list">
              {curationPendingReview && (
                <div className="curation-callout">
                  <div>
                    <strong>Weekly curation draft ready</strong>
                    <span>{curationNotes}</span>
                  </div>
                  <button type="button" className="model-picker-secondary" onClick={() => setActiveTab('review')}>
                    Review
                  </button>
                </div>
              )}
              {presets.map((preset) => (
                <PresetRow
                  key={preset.id}
                  preset={preset}
                  selected={localActiveGroupId === preset.id}
                  modelMap={modelMap}
                  onSelect={selectPreset}
                  onCustomize={saveCustomCopy}
                />
              ))}
            </div>
          )}

          {!loading && activeTab === 'custom' && (
            <div className="custom-groups">
              <div className="custom-groups-header">
                <div>
                  <h3>Custom groups</h3>
                  <p>Save curated copies or hand-picked model sets with your own chairman.</p>
                </div>
                <button type="button" className="model-picker-primary" onClick={() => saveCustomCopy()}>
                  Save current as custom
                </button>
              </div>
              {customGroups.length === 0 ? (
                <div className="selected-empty">No custom councils yet. Pick a curated preset, adjust it, then save a custom copy.</div>
              ) : (
                customGroups.map((group) => (
                  <button
                    type="button"
                    key={group.id}
                    className={`custom-group-row${localActiveGroupId === group.id ? ' selected' : ''}`}
                    onClick={() => selectCustom(group)}
                  >
                    <span>
                      <strong>{group.name}</strong>
                      <small>Chairman: {shortModelName(group.chairman_model)} · {group.models.length} models</small>
                    </span>
                    <ChevronRight size={18} />
                  </button>
                ))
              )}
            </div>
          )}

          {!loading && activeTab === 'browse' && (
            <div className="model-browser">
              <div className="model-filters">
                <label>
                  <span>Search</span>
                  <div className="model-search-input">
                    <Search size={15} />
                    <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Claude, Grok, cheap, tools..." />
                  </div>
                </label>
                <label>
                  <span>Provider</span>
                  <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                    <option value="">All providers</option>
                    {providers.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label>
                  <span>Price</span>
                  <select value={priceTier} onChange={(e) => setPriceTier(e.target.value)}>
                    <option value="">Any price</option>
                    {['Free', 'Cheap', 'Efficient', 'Premium', 'Expensive', 'Unknown'].map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Capability</span>
                  <select value={capability} onChange={(e) => setCapability(e.target.value)}>
                    <option value="">Any capability</option>
                    {CAPABILITY_FILTERS.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label>
                  <span>Context</span>
                  <select value={minContext} onChange={(e) => setMinContext(e.target.value)}>
                    <option value="">Any length</option>
                    <option value="128000">128k+</option>
                    <option value="200000">200k+</option>
                    <option value="1000000">1M+</option>
                  </select>
                </label>
              </div>
              <div className="model-browser-count">
                Showing {filteredModels.length} of {catalog.length} models
              </div>
              <div className="model-list">
                {filteredModels.slice(0, 160).map((model) => (
                  <ModelRow
                    key={model.id}
                    model={model}
                    selected={localCouncil.includes(model.id)}
                    chairman={localChairman}
                    onToggle={toggleModel}
                    onChairman={(modelId) => {
                      setLocalActiveGroupId('');
                      setLocalChairman(modelId);
                    }}
                  />
                ))}
                {filteredModels.length > 160 && (
                  <div className="model-list-limit">Refine filters to narrow the remaining {filteredModels.length - 160} models.</div>
                )}
              </div>
            </div>
          )}

          {!loading && activeTab === 'review' && (
            <div className="curation-review">
              <div className="curation-review-header">
                <div>
                  <h3>Curation Review</h3>
                  <p>Weekly drafts are prepared for review and do not change curated presets until approved.</p>
                  {curationState?.current_curation_model && (
                    <p>Current curator: {curationState.current_curation_model}</p>
                  )}
                </div>
                <button type="button" className="model-picker-primary" onClick={runCuration} disabled={curationBusy}>
                  {curationBusy ? 'Running...' : 'Run draft now'}
                </button>
              </div>
              {!curationDraft ? (
                <div className="selected-empty">No curation draft yet.</div>
              ) : (
                <div className="curation-draft">
                  <div className="curation-draft-meta">
                    <span>Status: {curationDraft.status}</span>
                    <span>Curation model: {curationDraft.curation_model}</span>
                    <span>Next curation model: {curationDraft.next_curation_model}</span>
                    {curationDraft.next_curator_status && (
                      <span>Next curator: {formatCurationText(curationDraft.next_curator_status).replace(/_/g, ' ')}</span>
                    )}
                    {curationCost && (
                      <span>Estimated review cost: {curationCost}</span>
                    )}
                  </div>
                  <p>{curationNotes}</p>
                  {curationRisks.length > 0 && (
                    <ul>
                      {curationRisks.map((risk) => <li key={risk}>{risk}</li>)}
                    </ul>
                  )}
                  {curationDraft.resolved_presets?.length > 0 && (
                    <div className="curation-preset-preview">
                      {curationDraft.resolved_presets.map((preset) => (
                        <CurationPresetPreview key={preset.id} preset={preset} modelMap={modelMap} />
                      ))}
                    </div>
                  )}
                  <button type="button" className="model-picker-primary" onClick={approveCuration} disabled={curationBusy || !curationPendingReview}>
                    {!curationPendingReview ? 'Approved' : 'Approve curated presets'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="model-picker-footer">
          <div className="model-picker-footer-status">
            {localCouncil.length === 0
              ? 'Select at least one council model.'
              : !localChairman
                ? 'Select a chairman model.'
                : `Ready: ${localCouncil.length} model${localCouncil.length === 1 ? '' : 's'}, chairman ${shortModelName(localChairman)}${normalEstimate ? `, normal question ${normalEstimate}` : ''}.`}
          </div>
          <button type="button" className="model-picker-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="model-picker-primary" onClick={apply} disabled={localCouncil.length === 0 || !localChairman}>
            Apply council
          </button>
        </div>
      </div>
    </div>
  );
}
