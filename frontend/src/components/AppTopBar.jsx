import { ChevronDown, Layers3, Menu, Sparkles } from 'lucide-react';
import {
  abbreviateModelName,
  displayModelName,
  estimateCouncilCosts,
  presetNormalCost,
  resolveActiveCouncil,
  shortModelName,
} from '../modelUtils';
import './AppTopBar.css';

export default function AppTopBar({
  settings,
  modelMap,
  presets,
  onOpenModels,
  onOpenConversations,
}) {
  const selectedModels = settings?.council_models || [];
  const chairman = settings?.chairman_model || '';
  const active = resolveActiveCouncil(settings, presets);
  const fallbackEstimate = estimateCouncilCosts(selectedModels, chairman, modelMap);
  const presetEstimate = active.selectionMatchesPreset ? presetNormalCost(active.preset) : null;
  const estimate = presetEstimate || fallbackEstimate?.display || 'Pricing unavailable';
  const catalogLoaded = (modelMap?.size || 0) > 0;
  const mobileModelSlots = selectedModels.slice(0, 4);
  const mobileOverflowCount = Math.max(selectedModels.length - mobileModelSlots.length, 0);
  const mobileChairmanLabel = abbreviateModelName(chairman, modelMap) || 'None';

  return (
    <header className="app-topbar">
      <button
        type="button"
        className="app-topbar-icon app-topbar-menu"
        onClick={onOpenConversations}
        aria-label="Open conversations"
      >
        <Menu size={19} />
      </button>

      <div className="app-topbar-command">
        <div className="app-topbar-council-row">
          <div className="app-topbar-title-group">
            <div className="app-topbar-label">Active council</div>
            <button type="button" className="app-topbar-council-button" onClick={onOpenModels}>
              <span>{active.name}</span>
              <ChevronDown size={16} />
            </button>
            <div className="app-topbar-mobile-summary">
              <span className="app-topbar-mobile-chairman">Chair: {mobileChairmanLabel}</span>
              <span aria-hidden="true">·</span>
              <span>
                {selectedModels.length} model{selectedModels.length === 1 ? '' : 's'}
              </span>
            </div>
          </div>
          <span className="app-topbar-badge">{active.badge}</span>
        </div>

        <div className="app-topbar-models" aria-label="Selected council models">
          {selectedModels.map((modelId) => (
            <span
              className={`app-topbar-chip${catalogLoaded && !modelMap.has(modelId) ? ' app-topbar-chip-muted' : ''}`}
              key={modelId}
            >
              {displayModelName(modelId, modelMap).replace(/^.*?:\s*/, '')}
            </span>
          ))}
        </div>

        <div className="app-topbar-mobile-models" aria-label="Selected council models">
          {mobileModelSlots.length > 0 ? (
            mobileModelSlots.map((modelId) => (
              <span
                className={`app-topbar-mobile-chip${catalogLoaded && !modelMap.has(modelId) ? ' app-topbar-mobile-chip-muted' : ''}`}
                key={modelId}
                title={displayModelName(modelId, modelMap)}
              >
                {abbreviateModelName(modelId, modelMap)}
              </span>
            ))
          ) : (
            <span className="app-topbar-mobile-chip app-topbar-mobile-chip-muted">
              No models
            </span>
          )}
          {mobileOverflowCount > 0 && (
            <span className="app-topbar-mobile-chip app-topbar-mobile-more">
              +{mobileOverflowCount}
            </span>
          )}
        </div>
      </div>

      <div className="app-topbar-detail app-topbar-chairman">
        <div className="app-topbar-label">Chairman</div>
        <div className="app-topbar-value chairman">
          <Sparkles size={18} />
          <span>{shortModelName(chairman) || 'None'}</span>
        </div>
      </div>

      <div className="app-topbar-detail app-topbar-cost">
        <div className="app-topbar-label">Est. cost (normal question)</div>
        <div className="app-topbar-value">{estimate}</div>
      </div>

      <button
        type="button"
        className="app-topbar-models-button"
        onClick={onOpenModels}
        aria-label="Open model picker"
      >
        <Layers3 size={17} />
        <span>Models</span>
      </button>
    </header>
  );
}
