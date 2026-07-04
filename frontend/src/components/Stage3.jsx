import { useState, useCallback, useMemo } from 'react';
import { AlertTriangle, Check, ChevronDown, ClipboardCopy, Share2, Star } from 'lucide-react';
import { abbreviateModelName, formatModelLabel, formatMoney, resolveModelLabel } from '../modelUtils';
import ProviderAvatar from './ProviderAvatar';
import MarkdownContent from './MarkdownContent';
import './Stage3.css';

async function copyTextToClipboard(content) {
  const text = content || '';

  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      console.warn('[clipboard] API failed:', err);
    }
  }

  try {
    const ta = document.createElement('textarea');
    ta.value = text;
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
    return ok;
  } catch (err) {
    console.error('[clipboard] Fallback copy failed:', err);
    return false;
  }
}

function buildSharePayload(text, chairmanLabel) {
  const body = text?.trim() || '';
  const title = 'Council Verdict';
  const attribution = chairmanLabel ? ` · ${chairmanLabel}` : '';
  return {
    title,
    text: `Council Verdict${attribution}\n\n${body}`,
  };
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);

  const handleCopy = useCallback(async () => {
    setError(false);
    const ok = await copyTextToClipboard(text);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      return;
    }
    setError(true);
    setTimeout(() => setError(false), 3000);
  }, [text]);

  return (
    <button
      type="button"
      className={`verdict-action-btn copy-synthesis-btn${error ? ' copy-error' : ''}`}
      onClick={handleCopy}
      title={error ? 'Copy failed — try selecting text manually' : 'Copy to clipboard'}
      aria-label={
        copied
          ? 'Copied to clipboard'
          : error
            ? 'Copy failed — try selecting text manually'
            : 'Copy verdict to clipboard'
      }
    >
      {copied
        ? <><Check size={14} aria-hidden="true" /><span className="verdict-action-btn-label">Copied!</span></>
        : error
          ? <><ClipboardCopy size={14} aria-hidden="true" /><span className="verdict-action-btn-label">Failed</span></>
          : <><ClipboardCopy size={14} aria-hidden="true" /><span className="verdict-action-btn-label">Copy</span></>
      }
    </button>
  );
}

function ShareButton({ text, chairmanLabel }) {
  const [status, setStatus] = useState('idle');
  const canNativeShare = typeof navigator !== 'undefined' && typeof navigator.share === 'function';

  const handleShare = useCallback(async () => {
    const payload = buildSharePayload(text, chairmanLabel);
    setStatus('idle');

    if (canNativeShare) {
      try {
        await navigator.share(payload);
        setStatus('shared');
        setTimeout(() => setStatus('idle'), 2000);
        return;
      } catch (err) {
        if (err?.name === 'AbortError') return;
        console.warn('[ShareButton] Native share failed:', err);
      }
    }

    const ok = await copyTextToClipboard(payload.text);
    if (ok) {
      setStatus('copied');
      setTimeout(() => setStatus('idle'), 2000);
      return;
    }

    setStatus('error');
    setTimeout(() => setStatus('idle'), 3000);
  }, [canNativeShare, chairmanLabel, text]);

  const label = status === 'shared'
    ? 'Shared!'
    : status === 'copied'
      ? 'Copied!'
      : status === 'error'
        ? 'Failed'
        : 'Share';

  return (
    <button
      type="button"
      className={`verdict-action-btn share-synthesis-btn${status === 'error' ? ' share-error' : ''}`}
      onClick={handleShare}
      title={
        status === 'error'
          ? 'Share failed — try copy instead'
          : canNativeShare
            ? 'Share verdict'
            : 'Copy formatted verdict for sharing'
      }
      aria-label={
        status === 'shared'
          ? 'Shared successfully'
          : status === 'copied'
            ? 'Copied formatted verdict for sharing'
            : status === 'error'
              ? 'Share failed — try copy instead'
              : 'Share verdict'
      }
    >
      {status === 'shared' || status === 'copied'
        ? <><Check size={14} aria-hidden="true" /><span className="verdict-action-btn-label">{label}</span></>
        : <><Share2 size={14} aria-hidden="true" /><span className="verdict-action-btn-label">{label}</span></>
      }
    </button>
  );
}

function formatStageLabel(stage) {
  const labels = {
    stage1: 'Stage 1',
    stage2: 'Stage 2',
    stage3: 'Stage 3',
  };
  return labels[stage] || stage || 'Call';
}

const STAGE_META = {
  stage1: { title: 'Stage 1', subtitle: 'Individual answers' },
  stage2: { title: 'Stage 2', subtitle: 'Peer rankings' },
  stage3: { title: 'Stage 3', subtitle: 'Final synthesis' },
};
const EMPTY_CALLS = [];

function sumStageCost(calls) {
  let total = 0;
  let hasPriced = false;
  for (const call of calls) {
    if (call.cost_usd !== null && call.cost_usd !== undefined) {
      total += Number(call.cost_usd);
      hasPriced = true;
    }
  }
  return hasPriced ? total : null;
}

function sumStageTokens(calls) {
  return calls.reduce((sum, call) => sum + Number(call.total_tokens || 0), 0);
}

function groupCallsByStage(calls) {
  const order = ['stage1', 'stage2', 'stage3'];
  return order
    .map((stage) => {
      const stageCalls = calls.filter((call) => call.stage === stage);
      if (stageCalls.length === 0) return null;
      return {
        stage,
        meta: STAGE_META[stage] || { title: formatStageLabel(stage), subtitle: '' },
        calls: stageCalls,
        totalUsd: sumStageCost(stageCalls),
        totalTokens: sumStageTokens(stageCalls),
      };
    })
    .filter(Boolean);
}

function finiteMoney(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function displayCostSummaryForBilling(costSummary, billingReceipt) {
  const appCharge = finiteMoney(billingReceipt?.actual_app_cost_usd);
  if (appCharge === null) return costSummary;

  const calls = costSummary?.calls || [];
  const rawCallTotal = calls.reduce((sum, call) => {
    const cost = finiteMoney(call.cost_usd);
    return cost === null ? sum : sum + cost;
  }, 0);
  const ratio = rawCallTotal > 0 ? appCharge / rawCallTotal : null;

  return {
    ...(costSummary || {}),
    total_usd: appCharge,
    calls: calls.map((call) => {
      const cost = finiteMoney(call.cost_usd);
      if (cost === null || ratio === null) return call;
      return { ...call, cost_usd: cost * ratio };
    }),
    display_mode: 'managed_app_charge',
  };
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

function CostCallRow({ call }) {
  const modelId = call.resolved_model || call.requested_model;
  const shortName = abbreviateModelName(modelId) || formatModelLabel(modelId);

  return (
    <div className="actual-cost-row">
      <ProviderAvatar
        className="actual-cost-row-avatar"
        modelId={modelId}
        aria-hidden="true"
      />
      <div className="actual-cost-row-main">
        <strong title={formatModelLabel(modelId)}>{shortName}</strong>
        <small>{formatTokens(call)}</small>
      </div>
      <span className={`actual-cost-row-value actual-cost-row-value--${call.status || 'unpriced'}`}>
        {formatCallCost(call)}
      </span>
    </div>
  );
}

function CostSummary({ costSummary, billingReceipt }) {
  const [expanded, setExpanded] = useState(false);
  const displayCostSummary = useMemo(
    () => displayCostSummaryForBilling(costSummary, billingReceipt),
    [costSummary, billingReceipt],
  );
  const calls = displayCostSummary?.calls || EMPTY_CALLS;
  const stageGroups = useMemo(
    () => groupCallsByStage(calls),
    [calls],
  );
  const hasDisplayTotal = displayCostSummary?.total_usd !== null &&
    displayCostSummary?.total_usd !== undefined;

  if (!displayCostSummary || (calls.length === 0 && !hasDisplayTotal)) {
    return (
      <div className="actual-cost actual-cost--empty" aria-label="Actual cost">
        <div className="actual-cost-bar">
          <div className="actual-cost-heading">
            <span className="actual-cost-kicker">Actual answer cost</span>
            <strong className="actual-cost-total">Cost unavailable for older run</strong>
          </div>
        </div>
      </div>
    );
  }

  const isManagedCharge = displayCostSummary.display_mode === 'managed_app_charge';
  const total = hasDisplayTotal
    ? formatMoney(Number(displayCostSummary.total_usd))
    : null;
  const unpriced = Number(displayCostSummary.unpriced_calls_count || 0);
  const failed = Number(displayCostSummary.failed_calls_count || 0);
  const totalTokens = Number(displayCostSummary.total_tokens || 0);

  let totalLabel = 'Cost unavailable';
  if (total && unpriced > 0) {
    totalLabel = `${total} tracked · ${unpriced} unpriced`;
  } else if (total) {
    totalLabel = total;
  } else if (unpriced > 0) {
    totalLabel = `${unpriced} unpriced`;
  }
  if (failed > 0) {
    totalLabel = `${totalLabel} · ${failed} failed`;
  }

  const metaParts = [];
  if (isManagedCharge) {
    metaParts.push('LLM Council Balance');
    const remainingBalance = finiteMoney(billingReceipt?.remaining_balance_usd);
    if (remainingBalance !== null) {
      metaParts.push(`Remaining balance ${formatMoney(remainingBalance)}`);
    }
  }
  if (calls.length > 0) {
    metaParts.push(`${calls.length} call${calls.length === 1 ? '' : 's'}`);
  }
  if (totalTokens > 0) {
    metaParts.push(`${totalTokens.toLocaleString()} tokens`);
  }

  return (
    <div className={`actual-cost${expanded ? ' actual-cost--expanded' : ''}`} aria-label="Actual cost">
      <div className="actual-cost-bar">
        <div className="actual-cost-heading">
          <span className="actual-cost-kicker">Actual answer cost</span>
          <strong className="actual-cost-total">{totalLabel}</strong>
          <span className="actual-cost-meta">{metaParts.join(' · ')}</span>
        </div>
        {calls.length > 0 && (
          <button
            type="button"
            className="actual-cost-expand-btn"
            onClick={() => setExpanded((open) => !open)}
            aria-expanded={expanded}
            aria-controls="actual-cost-breakdown"
          >
            <span>{expanded ? 'Hide breakdown' : 'Show breakdown'}</span>
            <ChevronDown size={14} aria-hidden="true" className="actual-cost-chevron" />
          </button>
        )}
      </div>
      {expanded && calls.length > 0 && (
        <div id="actual-cost-breakdown" className="actual-cost-breakdown">
          <div className="actual-cost-stages">
            {stageGroups.map((group) => (
              <section className="actual-cost-stage-card" key={group.stage} aria-label={group.meta.title}>
                <header className="actual-cost-stage-head">
                  <div className="actual-cost-stage-title">
                    <strong>{group.meta.title}</strong>
                    <span>{group.meta.subtitle}</span>
                  </div>
                  <div className="actual-cost-stage-total">
                    <strong>
                      {group.totalUsd !== null ? formatMoney(group.totalUsd) : '—'}
                    </strong>
                    {group.totalTokens > 0 && (
                      <small>{group.totalTokens.toLocaleString()} tokens</small>
                    )}
                  </div>
                </header>
                <div className="actual-cost-stage-rows">
                  {group.calls.map((call, index) => (
                    <CostCallRow
                      key={`${group.stage}-${call.requested_model}-${index}`}
                      call={call}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Stage3({ finalResponse, costSummary, billingReceipt, hero = false, modelMap }) {
  if (!finalResponse) {
    return null;
  }

  const isFallback = finalResponse.used_fallback ||
    finalResponse.response?.startsWith('⚠️');
  const chairmanModel = finalResponse.model.split(' (')[0];
  const chairmanLabel = resolveModelLabel(chairmanModel, modelMap);
  const chairmanTitle = formatModelLabel(chairmanModel);

  return (
    <div className={`stage stage3${hero ? ' stage3--hero' : ''}${isFallback ? ' stage3-fallback' : ''}`}>
      <div className="stage3-header stage3-header--sticky">
        <div className="stage3-icon">
          {isFallback ? (
            <AlertTriangle size={16} aria-hidden="true" />
          ) : (
            <Star size={16} aria-hidden="true" />
          )}
        </div>
        <div className="stage3-title-group">
          <h3 className="stage-title">{isFallback ? 'Partial Result' : 'Council Verdict'}</h3>
          <div
            className="chairman-label"
            title={chairmanTitle !== chairmanLabel ? chairmanTitle : undefined}
          >
            {isFallback ? 'Chairman unavailable — ' : 'Synthesized by '}
            {chairmanLabel}
          </div>
        </div>
        <div className="stage3-header-actions">
          <CopyButton text={finalResponse.response} />
          <ShareButton text={finalResponse.response} chairmanLabel={chairmanLabel} />
        </div>
      </div>
      <div className="final-response">
        <div className="final-answer-toolbar">
          <CostSummary costSummary={costSummary} billingReceipt={billingReceipt} />
        </div>
        <MarkdownContent className="final-text">
          {finalResponse.response}
        </MarkdownContent>
      </div>
    </div>
  );
}
