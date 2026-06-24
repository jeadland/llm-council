import { ChevronDown, Layers3, Menu, Sparkles } from 'lucide-react';
import { displayModelName, estimateCouncilCosts, presetNormalCost, shortModelName } from '../modelUtils';
import './AppTopBar.css';

function activeCouncilName(settings, presets) {
  const activeId = settings?.active_model_group_id;
  const custom = settings?.custom_model_groups?.find((group) => group.id === activeId);
  if (custom) return { name: custom.name, badge: 'Custom' };
  const preset = presets?.find((item) => item.id === activeId);
  if (preset) return { name: preset.name, badge: preset.badge || 'Curated', preset };
  const matched = presets?.find((presetItem) => {
    const models = presetItem.models || [];
    const selected = settings?.council_models || [];
    return models.length === selected.length && models.every((model) => selected.includes(model));
  });
  if (matched) return { name: matched.name, badge: matched.badge || 'Curated', preset: matched };
  return { name: 'Custom Council', badge: 'Custom' };
}

export default function AppTopBar({
  settings,
  modelMap,
  presets,
  onOpenModels,
  onOpenConversations,
}) {
  const selectedModels = settings?.council_models || [];
  const chairman = settings?.chairman_model || '';
  const active = activeCouncilName(settings, presets);
  const fallbackEstimate = estimateCouncilCosts(selectedModels, chairman, modelMap);
  const estimate = presetNormalCost(active.preset) || fallbackEstimate?.display || 'Pricing unavailable';

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
          </div>
          <span className="app-topbar-badge">{active.badge}</span>
        </div>

        <div className="app-topbar-models" aria-label="Selected council models">
          {selectedModels.map((modelId) => (
            <span className="app-topbar-chip" key={modelId}>
              {displayModelName(modelId, modelMap).replace(/^.*?:\s*/, '')}
            </span>
          ))}
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
