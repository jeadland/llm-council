import { ChevronDown, Menu } from 'lucide-react';
import {
  estimateCouncilCosts,
  providerMeta,
  presetNormalCost,
  resolveActiveCouncil,
  shortModelName,
} from '../modelUtils';
import ProviderAvatar from './ProviderAvatar';
import './AppTopBar.css';

const BRAND_ICON_URL = `${import.meta.env.BASE_URL}images/llm-council-icon.svg`;

export default function AppTopBar({
  settings,
  modelMap,
  presets,
  onOpenModels,
  onOpenConversations,
  sidebarPinned = false,
}) {
  const selectedModels = settings?.council_models || [];
  const chairman = settings?.chairman_model || '';
  const active = resolveActiveCouncil(settings, presets);
  const fallbackEstimate = estimateCouncilCosts(selectedModels, chairman, modelMap);
  const presetEstimate = active.selectionMatchesPreset ? presetNormalCost(active.preset) : null;
  const estimate = presetEstimate || fallbackEstimate?.display || 'Pricing unavailable';
  const chairmanLabel = shortModelName(chairman) || 'None';
  const modelCountLabel = `${selectedModels.length} model${selectedModels.length === 1 ? '' : 's'}`;
  const visibleProviders = selectedModels.slice(0, 4).map((modelId) => ({
    modelId,
    ...providerMeta(modelId),
  }));
  const overflowCount = Math.max(selectedModels.length - visibleProviders.length, 0);

  return (
    <header className="app-topbar">
      <div className="app-topbar-brand">
        <button
          type="button"
          className={`app-topbar-icon app-topbar-menu${sidebarPinned ? ' app-topbar-menu--active' : ''}`}
          onClick={onOpenConversations}
          aria-label={sidebarPinned ? 'Close conversations drawer' : 'Open conversations'}
          aria-pressed={sidebarPinned}
        >
          <Menu size={19} />
        </button>
        <button
          type="button"
          className="app-topbar-brand-link"
          onClick={onOpenConversations}
          aria-label="LLM Council conversations"
        >
          <img
            src={BRAND_ICON_URL}
            alt=""
            className="app-topbar-brand-icon"
            width="28"
            height="28"
          />
          <span className="app-topbar-brand-name">LLM Council</span>
        </button>
      </div>

      <div className="app-topbar-command">
        <button
          type="button"
          className="app-topbar-council-button"
          onClick={onOpenModels}
          aria-label="Open council setup"
        >
          <span className="app-topbar-council-name">{active.name}</span>
          <span className="app-topbar-provider-stack" aria-label="Selected providers">
            {visibleProviders.map((provider) => (
              <ProviderAvatar
                className="app-topbar-provider-avatar"
                key={provider.modelId}
                modelId={provider.modelId}
                title={provider.label}
              />
            ))}
            {overflowCount > 0 && (
              <span className="app-topbar-provider-avatar app-topbar-provider-more">
                +{overflowCount}
              </span>
            )}
          </span>
          <span className="app-topbar-council-meta">
            {modelCountLabel}
            <span aria-hidden="true">·</span>
            Chair: {chairmanLabel}
            <span aria-hidden="true">·</span>
            Est. {estimate}
          </span>
          <span className="app-topbar-badge">{active.badge}</span>
          <ChevronDown size={16} className="app-topbar-council-chevron" />
        </button>
      </div>
    </header>
  );
}
