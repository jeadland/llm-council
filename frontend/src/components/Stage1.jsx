import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import MarkdownContent from './MarkdownContent';
import './Stage1.css';

function formatModelLabel(model) {
  if (!model) return 'Unknown';
  const raw = model.startsWith('openrouter/') ? model.replace('openrouter/', '') : model;
  const nice = {
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
  };
  return nice[raw] || raw;
}

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
