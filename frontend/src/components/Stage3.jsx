import ReactMarkdown from 'react-markdown';
import './Stage3.css';

function formatModelLabel(model) {
  if (!model) return 'unknown';
  return model.startsWith('openrouter/') ? model.replace('openrouter/', '') : model;
}

export default function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {formatModelLabel(finalResponse.model)}
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
