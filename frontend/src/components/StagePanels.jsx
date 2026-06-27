import { formatModelLabel, providerMeta, resolveModelLabel } from '../modelUtils';
import './StagePanels.css';

export function StageIntro({ title, children, variant = 'info' }) {
  return (
    <div className={`stage-intro stage-intro--${variant}`}>
      {title && <div className="stage-intro-title">{title}</div>}
      <div className="stage-intro-body">{children}</div>
    </div>
  );
}

export function ModelReviewerTabs({
  items,
  activeIndex,
  onChange,
  idPrefix = 'reviewer',
  ariaLabel = 'Select model',
  modelMap,
}) {
  return (
    <div className="model-reviewer-tabs" role="tablist" aria-label={ariaLabel}>
      {items.map((item, index) => {
        const meta = providerMeta(item.model);
        const label = resolveModelLabel(item.model, modelMap);
        const fullLabel = formatModelLabel(item.model);
        const isActive = index === activeIndex;
        return (
          <button
            key={item.model}
            type="button"
            role="tab"
            aria-selected={isActive}
            id={`${idPrefix}-tab-${index}`}
            aria-controls={`${idPrefix}-panel-${index}`}
            className={`model-reviewer-tab${isActive ? ' model-reviewer-tab--active' : ''}${item.invalid ? ' model-reviewer-tab--invalid' : ''}`}
            onClick={() => onChange(index)}
            title={fullLabel !== label ? fullLabel : label}
          >
            <span
              className="model-reviewer-tab-avatar"
              style={{ '--agent-color': meta.color }}
              aria-hidden="true"
            >
              {meta.glyph}
            </span>
            <span className="model-reviewer-tab-label">{label}</span>
          </button>
        );
      })}
    </div>
  );
}

export function ReviewerContentHeader({ model, subtitle, modelMap }) {
  const meta = providerMeta(model);
  const label = resolveModelLabel(model, modelMap);
  const fullLabel = formatModelLabel(model);
  return (
    <div className="reviewer-content-header">
      <span
        className="reviewer-content-avatar"
        style={{ '--agent-color': meta.color }}
        aria-hidden="true"
      >
        {meta.glyph}
      </span>
      <div className="reviewer-content-heading">
        <strong title={fullLabel !== label ? fullLabel : undefined}>{label}</strong>
        {subtitle && <span>{subtitle}</span>}
      </div>
    </div>
  );
}
