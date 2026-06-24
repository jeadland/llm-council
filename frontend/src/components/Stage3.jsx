import { useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { ClipboardCopy, Check } from 'lucide-react';
import { formatMoney } from '../modelUtils';
import './Stage3.css';

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);

  const handleCopy = useCallback(async () => {
    setError(false);
    const content = text || '';
    console.log('[CopyButton] Attempting copy, text length:', content.length);

    // Try modern Clipboard API first (requires secure context: HTTPS or localhost)
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(content);
        console.log('[CopyButton] Clipboard API succeeded');
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        return;
      } catch (err) {
        console.warn('[CopyButton] Clipboard API failed:', err);
      }
    } else {
      console.warn('[CopyButton] Clipboard API unavailable (not secure context or missing API)');
    }

    // Fallback: create a temporary textarea and use execCommand('copy')
    try {
      const ta = document.createElement('textarea');
      ta.value = content;
      ta.style.position = 'fixed';
      ta.style.top = '0';
      ta.style.left = '0';
      ta.style.opacity = '0';
      ta.setAttribute('readonly', '');
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      if (ok) {
        console.log('[CopyButton] execCommand fallback succeeded');
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } else {
        throw new Error('execCommand returned false');
      }
    } catch (err2) {
      console.error('[CopyButton] Fallback copy also failed:', err2);
      setError(true);
      setTimeout(() => setError(false), 3000);
    }
  }, [text]);

  return (
    <button
      className={`copy-synthesis-btn${error ? ' copy-error' : ''}`}
      onClick={handleCopy}
      title={error ? 'Copy failed — try selecting text manually' : 'Copy to clipboard'}
    >
      {copied
        ? <><Check size={14} /> Copied!</>
        : error
          ? <><ClipboardCopy size={14} /> Failed</>
          : <><ClipboardCopy size={14} /> Copy</>
      }
    </button>
  );
}

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

function formatStageLabel(stage) {
  const labels = {
    stage1: 'Stage 1',
    stage2: 'Stage 2',
    stage3: 'Stage 3',
  };
  return labels[stage] || stage || 'Call';
}

function formatCallCost(call) {
  if (call.cost_usd !== null && call.cost_usd !== undefined) {
    return formatMoney(Number(call.cost_usd));
  }
  if (call.status === 'failed') return 'failed';
  return 'unpriced';
}

function formatTokens(call) {
  if (call.total_tokens) return `${call.total_tokens.toLocaleString()} tokens`;
  const pieces = [];
  if (call.prompt_tokens) pieces.push(`${call.prompt_tokens.toLocaleString()} in`);
  if (call.completion_tokens) pieces.push(`${call.completion_tokens.toLocaleString()} out`);
  return pieces.length ? pieces.join(' / ') : 'tokens unavailable';
}

function CostSummary({ costSummary }) {
  const calls = costSummary?.calls || [];

  if (!costSummary || calls.length === 0) {
    return (
      <div className="actual-cost" aria-label="Actual cost">
        <span>Actual cost</span>
        <strong>Cost unavailable for older run</strong>
      </div>
    );
  }

  const total = costSummary.total_usd !== null && costSummary.total_usd !== undefined
    ? formatMoney(Number(costSummary.total_usd))
    : null;
  const unpriced = Number(costSummary.unpriced_calls_count || 0);
  const failed = Number(costSummary.failed_calls_count || 0);
  let label = 'Cost unavailable';
  if (total && unpriced > 0) {
    label = `${total} tracked · ${unpriced} call${unpriced === 1 ? '' : 's'} unpriced`;
  } else if (total) {
    label = total;
  } else if (unpriced > 0) {
    label = `${unpriced} call${unpriced === 1 ? '' : 's'} unpriced`;
  }
  if (failed > 0) {
    label = `${label} · ${failed} failed`;
  }

  return (
    <div className="actual-cost" aria-label="Actual cost">
      <span>Actual cost</span>
      <strong>{label}</strong>
      <details className="actual-cost-details">
        <summary>Details</summary>
        <div className="actual-cost-call-list">
          {calls.map((call, index) => (
            <div className="actual-cost-call" key={`${call.stage}-${call.requested_model}-${index}`}>
              <div>
                <span className="actual-cost-stage">{formatStageLabel(call.stage)}</span>
                <strong>{formatModelLabel(call.resolved_model || call.requested_model)}</strong>
                <small>{formatTokens(call)}</small>
              </div>
              <span className={`actual-cost-value actual-cost-value--${call.status || 'unpriced'}`}>
                {formatCallCost(call)}
              </span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

export default function Stage3({ finalResponse, costSummary }) {
  if (!finalResponse) {
    return null;
  }

  const isFallback = finalResponse.used_fallback ||
    finalResponse.response?.startsWith('⚠️');

  return (
    <div className={`stage stage3${isFallback ? ' stage3-fallback' : ''}`}>
      <div className="stage3-header">
        <div className="stage3-icon">
          {isFallback ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
            </svg>
          )}
        </div>
        <div>
          <h3 className="stage-title">{isFallback ? 'Partial Result' : 'Council Verdict'}</h3>
          <div className="chairman-label">
            {isFallback ? 'Chairman unavailable — ' : 'Synthesized by '}
            {formatModelLabel(finalResponse.model.split(' (')[0])}
          </div>
          <CostSummary costSummary={costSummary} />
        </div>
      </div>
      <div className="final-response">
        <div className="copy-row copy-row-top">
          <CopyButton text={finalResponse.response} />
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
        <div className="copy-row copy-row-bottom">
          <CopyButton text={finalResponse.response} />
        </div>
      </div>
    </div>
  );
}
