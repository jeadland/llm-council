import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, ChevronRight, CopyPlus, Loader2, Search, Sparkles, X } from 'lucide-react';
import { api } from '../api';
import {
  buildCurationSummary,
  diffCurationPresets,
  displayModelName,
  estimateCouncilCosts,
  formatContext,
  formatCurationCost,
  formatCurationDate,
  formatCurationList,
  formatCurationStatusLabel,
  formatCurationText,
  formatCurationWarnings,
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

function ModelPill({ modelId, modelMap, muted = false, added = false }) {
  const model = modelMap.get(modelId);
  return (
    <span className={`model-picker-pill${muted ? ' muted' : ''}${added ? ' added' : ''}`}>
      {model?.name?.replace(/^.*?:\s*/, '') || shortModelName(modelId)}
      {!model && <span className="model-picker-pill-warning">stale</span>}
    </span>
  );
}

function CurationPresetChangeCard({ diff, modelMap }) {
  const { proposed, changed, chairmanChanged, addedModels, removedModels, missingModels } = diff;
  const stableModels = (proposed.models || []).filter(
    (modelId) => !addedModels.includes(modelId),
  );

  return (
    <article className={`curation-change-card${changed ? ' curation-change-card--changed' : ''}`}>
      <header className="curation-change-head">
        <strong>{diff.name}</strong>
        <span className={`curation-change-badge${changed ? '' : ' muted'}`}>
          {changed ? 'Updated' : 'Unchanged'}
        </span>
      </header>
      {chairmanChanged && (
        <p className="curation-change-line">
          Chairman: {shortModelName(diff.current?.chairman_model)} → {shortModelName(proposed.chairman_model)}
        </p>
      )}
      <div className="curation-change-models" aria-label={`${diff.name} model lineup`}>
        {removedModels.map((modelId) => (
          <ModelPill key={`removed-${modelId}`} modelId={modelId} modelMap={modelMap} muted />
        ))}
        {stableModels.map((modelId) => (
          <ModelPill key={modelId} modelId={modelId} modelMap={modelMap} />
        ))}
        {addedModels.map((modelId) => (
          <ModelPill key={`added-${modelId}`} modelId={modelId} modelMap={modelMap} added />
        ))}
        {missingModels.map((modelId) => (
          <ModelPill key={`missing-${modelId}`} modelId={modelId} modelMap={modelMap} muted />
        ))}
      </div>
      {missingModels.length > 0 && (
        <p className="curation-change-note">
          {missingModels.length} proposed model{missingModels.length === 1 ? '' : 's'} not found in the live catalog.
        </p>
      )}
    </article>
  );
}

function CurationTechnicalDetails({ draft, curationState, curationCost }) {
  const [open, setOpen] = useState(false);
  const technicalNotes = formatCurationText(draft?.notes, '');
  const technicalRisks = formatCurationList(draft?.risks);
  const hasDetails = Boolean(
    technicalNotes
    || technicalRisks.length > 0
    || draft?.curation_model
    || draft?.next_curation_model
    || draft?.recommended_enhancer_model
    || curationCost,
  );

  if (!hasDetails) return null;

  return (
    <div className={`curation-technical${open ? ' curation-technical--open' : ''}`}>
      <button
        type="button"
        className="curation-technical-toggle"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span>Technical details</span>
        <ChevronDown size={14} aria-hidden="true" className="curation-technical-chevron" />
      </button>
      {open && (
        <div className="curation-technical-body">
          <div className="curation-draft-meta">
            {draft?.status && <span>Status: {draft.status}</span>}
            {draft?.trigger && <span>Trigger: {String(draft.trigger).replace(/_/g, ' ')}</span>}
            {draft?.created_at && <span>Created: {formatCurationDate(draft.created_at)}</span>}
            {draft?.curation_model && <span>Curator model: {draft.curation_model}</span>}
            {draft?.next_curation_model && <span>Next curator model: {draft.next_curation_model}</span>}
            {draft?.next_curator_status && (
              <span>Next curator: {formatCurationText(draft.next_curator_status).replace(/_/g, ' ')}</span>
            )}
            {draft?.recommended_enhancer_model && (
              <span>Recommended enhancer model: {draft.recommended_enhancer_model}</span>
            )}
            {curationState?.current_curation_model && (
              <span>Current curator: {curationState.current_curation_model}</span>
            )}
            {curationCost && <span>Estimated review cost: {curationCost}</span>}
          </div>
          {technicalNotes && <p className="curation-technical-notes">{technicalNotes}</p>}
          {technicalRisks.length > 0 && (
            <ul className="curation-technical-risks">
              {technicalRisks.map((risk) => <li key={risk}>{risk}</li>)}
            </ul>
          )}
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
  const curationPresetDiffs = useMemo(
    () => diffCurationPresets(presets, curationDraft?.resolved_presets),
    [presets, curationDraft?.resolved_presets],
  );
  const curationSummary = useMemo(
    () => buildCurationSummary({
      draft: curationDraft,
      presetDiffs: curationPresetDiffs,
    }),
    [curationDraft, curationPresetDiffs],
  );
  const curationWarnings = useMemo(
    () => formatCurationWarnings(curationDraft?.risks),
    [curationDraft?.risks],
  );
  const curationCost = formatCurationCost(curationDraft?.estimated_llm_cost);
  const curationStatusLabel = formatCurationStatusLabel(curationDraft?.status, {
    approved: Boolean(curationDraft?.approved_at),
  });
  const changedPresetCount = curationPresetDiffs.filter((diff) => diff.changed).length;

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
      setActiveTab('curation');
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
            ['curation', 'Weekly curation', 'Curation'],
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
              {id === 'curation' && curationPendingReview && <span className="tab-count">1</span>}
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
                    <strong>Preset update ready</strong>
                    <span>
                      {changedPresetCount > 0
                        ? `${changedPresetCount} curated preset${changedPresetCount === 1 ? '' : 's'} have proposed lineup changes.`
                        : 'A weekly curation draft is ready to review.'}
                    </span>
                  </div>
                  <button type="button" className="model-picker-secondary" onClick={() => setActiveTab('curation')}>
                    Open curation
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

          {!loading && activeTab === 'curation' && (
            <div className="curation-review">
              <div className="curation-review-header">
                <div>
                  <h3>Weekly curation</h3>
                  <p>Review proposed preset updates from the live OpenRouter catalog. Nothing changes until you approve.</p>
                </div>
                <button type="button" className="model-picker-primary" onClick={runCuration} disabled={curationBusy}>
                  {curationBusy ? 'Running...' : 'Run draft now'}
                </button>
              </div>
              {!curationDraft ? (
                <div className="selected-empty">No curation draft yet. Run a draft to compare proposed preset lineups against what is live today.</div>
              ) : (
                <div className="curation-draft">
                  <div className="curation-status-card">
                    <span className={`curation-status-badge curation-status-badge--${curationDraft.status || 'unknown'}`}>
                      {curationStatusLabel}
                    </span>
                    <p>{curationSummary}</p>
                    {curationWarnings.length > 0 && (
                      <ul className="curation-warning-list">
                        {curationWarnings.map((warning) => <li key={warning}>{warning}</li>)}
                      </ul>
                    )}
                  </div>

                  {curationPresetDiffs.length > 0 && (
                    <section className="curation-changes" aria-label="Proposed preset changes">
                      <h4>Proposed preset changes</h4>
                      <div className="curation-change-list">
                        {curationPresetDiffs.map((diff) => (
                          <CurationPresetChangeCard key={diff.id} diff={diff} modelMap={modelMap} />
                        ))}
                      </div>
                    </section>
                  )}

                  <CurationTechnicalDetails
                    draft={curationDraft}
                    curationState={curationState}
                    curationCost={curationCost}
                  />

                  <button
                    type="button"
                    className="model-picker-primary curation-approve-btn"
                    onClick={approveCuration}
                    disabled={curationBusy || !curationPendingReview}
                  >
                    {!curationPendingReview ? 'Approved' : 'Approve preset updates'}
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
