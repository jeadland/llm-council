import { ChevronDown, Layers3, Menu } from 'lucide-react';
import {
  estimateCouncilCosts,
  providerMeta,
  presetNormalCost,
  resolveActiveCouncil,
  shortModelName,
} from '../modelUtils';
import './AppTopBar.css';

const LOGO_PROVIDERS = new Set([
  'anthropic',
  'openai',
  'google',
  'x-ai',
  'xai',
  'deepseek',
  'meta',
  'meta-llama',
  'mistral',
  'mistralai',
]);

function ProviderLogo({ provider }) {
  switch (provider) {
    case 'openai':
      return (
        <svg viewBox="0 0 24 24" className="app-topbar-provider-logo" aria-hidden="true">
          <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 4.1c2.2 0 3.9 1.7 3.9 3.8v.4l2.8 1.6c1.9 1.1 2.5 3.5 1.5 5.3-1.1 1.9-3.5 2.5-5.3 1.5l-.4-.2-2.8 1.6c-1.9 1.1-4.2.5-5.3-1.4-1.1-1.8-.5-4.2 1.3-5.3l.4-.2V8c0-2.2 1.7-3.9 3.9-3.9Z" />
            <path d="M8.3 8.7 12 6.6l3.7 2.1v4.2L12 15l-3.7-2.1V8.7Z" />
            <path d="M12 15v4.2" />
            <path d="m8.3 12.9-3.6 2.1" />
            <path d="m15.7 12.9 3.6 2.1" />
          </g>
        </svg>
      );
    case 'anthropic':
      return (
        <svg viewBox="0 0 24 24" className="app-topbar-provider-logo" aria-hidden="true">
          <path
            fill="currentColor"
            d="M12 4.2 20.2 20h-3.3l-1.6-3.3H8.7L7.1 20H3.8L12 4.2Zm-2.2 10h4.4L12 9.5l-2.2 4.7Z"
          />
        </svg>
      );
    case 'google':
      return (
        <svg viewBox="0 0 24 24" className="app-topbar-provider-logo" aria-hidden="true">
          <path fill="#4285f4" d="M22.6 12.2c0-.7-.1-1.4-.2-2H12v3.9h6c-.3 1.3-1 2.4-2 3.1v2.6h3.3c2.1-1.9 3.3-4.6 3.3-7.6Z" />
          <path fill="#34a853" d="M12 23c3 0 5.5-1 7.3-3.2L16 17.2c-.9.6-2.1 1-4 1-3 0-5.5-2-6.4-4.8H2.2v2.7C4 20.2 7.7 23 12 23Z" />
          <path fill="#fbbc05" d="M5.6 13.4c-.2-.7-.4-1.5-.4-2.4s.1-1.6.4-2.4V5.9H2.2A10.8 10.8 0 0 0 1 11c0 1.8.4 3.5 1.2 5.1l3.4-2.7Z" />
          <path fill="#ea4335" d="M12 3.8c1.6 0 3.1.6 4.2 1.7l3-3A10.2 10.2 0 0 0 12 1C7.7 1 4 3.8 2.2 5.9l3.4 2.7C6.5 5.8 9 3.8 12 3.8Z" />
        </svg>
      );
    case 'x-ai':
    case 'xai':
      return (
        <svg viewBox="0 0 24 24" className="app-topbar-provider-logo" aria-hidden="true">
          <path
            fill="currentColor"
            d="M5.7 5h3.2l3.1 4.7L15.8 5H19l-5.3 6.7L19.2 19H16l-3.5-5.1L8.4 19H5.2l5.7-7.1L5.7 5Z"
          />
        </svg>
      );
    case 'deepseek':
      return (
        <svg viewBox="0 0 24 24" className="app-topbar-provider-logo" aria-hidden="true">
          <path
            fill="currentColor"
            d="M5 4.8h7.2c4.4 0 7.8 3.1 7.8 7.2s-3.4 7.2-7.8 7.2H5V4.8Zm3.1 2.8v8.8h3.8c2.8 0 4.8-1.8 4.8-4.4s-2-4.4-4.8-4.4H8.1Z"
          />
          <path fill="#7f9dff" d="M11.5 10.8h8.3v2.5h-8.3z" />
        </svg>
      );
    case 'meta':
    case 'meta-llama':
      return (
        <svg viewBox="0 0 24 24" className="app-topbar-provider-logo" aria-hidden="true">
          <path
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            d="M3.5 15.5c1.3-5.1 3-7 5.1-7 1.6 0 2.7 1.1 3.4 2.2.8-1.1 1.9-2.2 3.4-2.2 2.1 0 3.8 1.9 5.1 7 .4 1.6-.3 3-1.7 3-1.8 0-3.8-3.3-6.8-7.8-3 4.5-5 7.8-6.8 7.8-1.4 0-2.1-1.4-1.7-3Z"
          />
        </svg>
      );
    case 'mistral':
    case 'mistralai':
      return (
        <svg viewBox="0 0 24 24" className="app-topbar-provider-logo" aria-hidden="true">
          <path fill="currentColor" d="M4 5h4v4H4V5Zm6 0h4v4h-4V5Zm6 0h4v4h-4V5ZM4 11h4v8H4v-8Zm6 3h4v5h-4v-5Zm6-3h4v8h-4v-8Z" />
        </svg>
      );
    default:
      return null;
  }
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
      <button
        type="button"
        className="app-topbar-icon app-topbar-menu"
        onClick={onOpenConversations}
        aria-label="Open conversations"
      >
        <Menu size={19} />
      </button>

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
              <span
                className={`app-topbar-provider-avatar${LOGO_PROVIDERS.has(provider.provider) ? ' app-topbar-provider-avatar--logo' : ''}`}
                key={provider.modelId}
                title={provider.label}
                style={{ "--provider-color": provider.color }}
              >
                <ProviderLogo provider={provider.provider} />
                {!LOGO_PROVIDERS.has(provider.provider) && provider.glyph}
              </span>
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

      <button
        type="button"
        className="app-topbar-models-button"
        onClick={onOpenModels}
        aria-label="Open council setup"
      >
        <Layers3 size={17} />
        <span>Setup</span>
      </button>
    </header>
  );
}
