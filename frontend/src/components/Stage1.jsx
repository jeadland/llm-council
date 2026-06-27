import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import MarkdownContent from './MarkdownContent';
import { formatModelLabel } from '../modelUtils';
import './Stage1.css';

function hitOutputLimit(response) {
  const costCall = response?.cost_call || {};
  const finishReason = String(costCall.finish_reason || '').toLowerCase();
  const nativeFinishReason = String(costCall.native_finish_reason || '').toLowerCase();
  return [finishReason, nativeFinishReason].some((reason) =>
    ['length', 'max_tokens', 'max_output_tokens'].includes(reason)
  );
}

export default function Stage1({ responses, defaultCollapsed = false }) {
  const [activeTab, setActiveTab] = useState(0);
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  if (!responses || responses.length === 0) {
    return null;
  }

  const summary =
    responses.length === 1
      ? `${formatModelLabel(responses[0].model)} responded`
      : `${responses.length} model responses`;

  return (
    <div className="stage stage1">
      <button
        type="button"
        className="collapse-toggle"
        aria-expanded={!collapsed}
        onClick={() => setCollapsed((v) => !v)}
      >
        <span className="collapse-title">
          <ChevronRight className="collapse-chevron" size={15} aria-hidden="true" />
          <span>Stage 1</span>
          <strong>Individual responses</strong>
        </span>
        <span className="collapse-summary">{summary}</span>
      </button>

      {!collapsed && (
        <>
          <div className="tabs">
            {responses.map((resp, index) => (
              <button
                key={index}
                className={`tab ${activeTab === index ? 'active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {formatModelLabel(resp.model)}
              </button>
            ))}
          </div>

          <div className="tab-content">
            <div className="model-name">{formatModelLabel(responses[activeTab].model)}</div>
            {hitOutputLimit(responses[activeTab]) && (
              <div className="stage1-limit-alert" role="status">
                This model reached the output limit, so its individual answer may be incomplete.
              </div>
            )}
            <MarkdownContent className="response-text">
              {responses[activeTab].response}
            </MarkdownContent>
          </div>
        </>
      )}
    </div>
  );
}
