import ReactMarkdown from 'react-markdown';
import './Stage3.css';

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
    'x-ai/grok-4.1-fast': 'Grok 4.1 Fast',
    'openai/gpt-5.2': 'GPT-5.2',
    'openai/gpt-5.2-chat': 'GPT-5.2 Chat',
    'openai/gpt-5.2-pro': 'GPT-5.2 Pro',
  };
  return nice[raw] || raw;
}

export default function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  return (
    <div className="stage stage3">
      <div className="stage3-header">
        <div className="stage3-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
          </svg>
        </div>
        <div>
          <h3 className="stage-title">Council Verdict</h3>
          <div className="chairman-label">
            Synthesized by {formatModelLabel(finalResponse.model)}
          </div>
        </div>
      </div>
      <div className="final-response">
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
