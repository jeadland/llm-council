import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Layers3, Menu, Sparkles } from 'lucide-react';
import {
  abbreviateModelName,
  displayModelName,
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
  const catalogLoaded = (modelMap?.size || 0) > 0;
  const [showOverflow, setShowOverflow] = useState(false);
  const overflowRef = useRef(null);
  const visibleModels = selectedModels.slice(0, 4);
  const overflowModels = selectedModels.slice(4);
  const mobileModelSlots = selectedModels.slice(0, 4);
  const mobileOverflowCount = Math.max(selectedModels.length - mobileModelSlots.length, 0);
  const mobileChairmanLabel = abbreviateModelName(chairman, modelMap) || 'None';

  useEffect(() => {
    if (!showOverflow) return;
    const close = (event) => {
      if (!overflowRef.current?.contains(event.target)) {
        setShowOverflow(false);
      }
    };
    window.addEventListener('pointerdown', close);
    return () => window.removeEventListener('pointerdown', close);
  }, [showOverflow]);

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

      <div className="app-topbar-models" aria-label="Selected council models">
        {visibleModels.map((modelId) => (
          <span
            className={`app-topbar-chip${catalogLoaded && !modelMap.has(modelId) ? ' app-topbar-chip-muted' : ''}`}
            key={modelId}
            title={displayModelName(modelId, modelMap)}
          >
            {displayModelName(modelId, modelMap).replace(/^.*?:\s*/, '')}
          </span>
        ))}
        {overflowModels.length > 0 && (
          <div className="app-topbar-overflow" ref={overflowRef}>
            <button
              type="button"
              className="app-topbar-chip app-topbar-chip-more"
              onClick={() => setShowOverflow((open) => !open)}
              aria-expanded={showOverflow}
              aria-label={`Show ${overflowModels.length} more models`}
            >
              +{overflowModels.length}
            </button>
            {showOverflow && (
              <div className="app-topbar-overflow-menu" role="menu">
                {overflowModels.map((modelId) => (
                  <div className="app-topbar-overflow-row" key={modelId} role="menuitem">
                    {displayModelName(modelId, modelMap)}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="app-topbar-value chairman app-topbar-chairman">
        <Sparkles size={17} />
        <span>{shortModelName(chairman) || 'None'}</span>
      </div>

      <button
        type="button"
        className="app-topbar-models-button"
        onClick={onOpenModels}
        aria-label="Open model picker"
      >
        <Layers3 size={17} />
        <span>Edit Council</span>
      </button>
    </header>
  );
}
