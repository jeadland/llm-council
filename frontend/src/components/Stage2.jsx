import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import MarkdownContent from './MarkdownContent';
import AggregateRankings from './AggregateRankings';
import { formatModelLabel } from '../modelUtils';
import './Stage2.css';

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Replace each "Response X" with the actual model name
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = formatModelLabel(model);
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

export default function Stage2({
  rankings,
  labelToModel,
  aggregateRankings,
  stage2Execution,
  error,
  defaultCollapsed = false,
}) {
  const [activeTab, setActiveTab] = useState(0);
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const completedRankingRows = rankings || [];

  if (!rankings && !stage2Execution && !error) {
    return null;
  }

  const expectedRankings = Number(stage2Execution?.expected_rankings_count || completedRankingRows.length);
  const completedRankings = Number(stage2Execution?.completed_rankings_count || completedRankingRows.length);
  const failedModels = Array.isArray(stage2Execution?.failed_models)
    ? stage2Execution.failed_models
    : [];
  const pendingModels = Array.isArray(stage2Execution?.pending_models)
    ? stage2Execution.pending_models
    : [];
  const missingModels = pendingModels.length > 0 ? pendingModels : failedModels;
  const attemptsByModel = stage2Execution?.attempts_by_model || {};
  const latestDiagnostics = stage2Execution?.latest_diagnostics || {};
  const maxAttempts = Number(stage2Execution?.max_attempts || 0);
  const timeoutSeconds = Number(stage2Execution?.timeout_seconds || 0);
  const isPartial = Boolean(stage2Execution?.is_partial) || completedRankings < expectedRankings;
  const voteLabel = `${completedRankings} of ${expectedRankings} peer ranking${expectedRankings === 1 ? '' : 's'}`;
  const topAggregate = aggregateRankings?.[0];
  const summary = topAggregate
    ? `${isPartial ? 'Partial · ' : ''}Top: ${formatModelLabel(topAggregate.model)} · ${topAggregate.average_rank.toFixed(2)} avg`
    : `${isPartial ? 'Partial · ' : ''}${voteLabel}`;

  return (
    <div className="stage stage2">
      <button
        type="button"
        className="collapse-toggle"
        aria-expanded={!collapsed}
        onClick={() => setCollapsed((v) => !v)}
      >
        <span className="collapse-title">
          <ChevronRight className="collapse-chevron" size={15} aria-hidden="true" />
          <span>Stage 2</span>
          <strong>Peer rankings</strong>
        </span>
        <span className="collapse-summary">{summary}</span>
      </button>

      {!collapsed && (
        <>
          <h4>Raw Evaluations</h4>
          <p className="stage-description">
            Each model evaluated all responses (anonymized as Response A, B, C, etc.) and provided rankings.
            Below, model names are shown in <strong>bold</strong> for readability, but the original evaluation used anonymous labels.
          </p>

          {isPartial && (
            <div className="stage2-partial-alert" role="status">
              <strong>Partial peer review:</strong> this run received {voteLabel}.{' '}
              {missingModels.length > 0 && (
                <span>
                  Missing: {missingModels.map(formatModelLabel).join(', ')}.
                </span>
              )}
              {maxAttempts > 0 && timeoutSeconds > 0 && (
                <span> Retrying up to {maxAttempts} times with a {timeoutSeconds}s timeout per reviewer.</span>
              )}
              {missingModels.length > 0 && maxAttempts > 0 && (
                <div className="stage2-diagnostic">
                  Attempts:{' '}
                  {missingModels.map((model) => (
                    <span key={model}>
                      {formatModelLabel(model)} {attemptsByModel[model] || 0}/{maxAttempts}
                    </span>
                  ))}
                </div>
              )}
              {missingModels.some((model) => latestDiagnostics[model]) && (
                <div className="stage2-diagnostic-list">
                  {missingModels.map((model) => {
                    const diagnostic = latestDiagnostics[model];
                    if (!diagnostic) return null;
                    const status = diagnostic.status_code ? ` ${diagnostic.status_code}` : '';
                    return (
                      <div key={model} className="stage2-diagnostic-row">
                        <strong>{formatModelLabel(model)}:</strong>{' '}
                        {diagnostic.error_type || 'unknown'}{status} from {diagnostic.provider_source || 'unknown'}
                        {diagnostic.message ? ` - ${diagnostic.message}` : ''}
                      </div>
                    );
                  })}
                </div>
              )}
              {error && (
                <div className="stage2-error-text">
                  {error}
                </div>
              )}
            </div>
          )}

          <div className="tabs">
            {completedRankingRows.map((rank, index) => (
              <button
                key={index}
                className={`tab ${activeTab === index ? 'active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {formatModelLabel(rank.model)}
              </button>
            ))}
          </div>

          {completedRankingRows.length > 0 && (
            <div className="tab-content">
              <div className="ranking-model">
                {formatModelLabel(completedRankingRows[activeTab].model)}
              </div>
              {completedRankingRows[activeTab].ranking_valid === false && (
                <div className="stage2-invalid-alert" role="status">
                  This peer review returned an invalid ranking and was not counted in aggregate scoring.
                  {completedRankingRows[activeTab].ranking_issues?.length > 0 && (
                    <div className="stage2-diagnostic-list">
                      {completedRankingRows[activeTab].ranking_issues.map((issue) => (
                        <div key={issue} className="stage2-diagnostic-row">{issue}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <MarkdownContent className="ranking-content">
                {deAnonymizeText(completedRankingRows[activeTab].ranking, labelToModel)}
              </MarkdownContent>

              {completedRankingRows[activeTab].parsed_ranking &&
               completedRankingRows[activeTab].parsed_ranking.length > 0 && (
                <div className="parsed-ranking">
                  <strong>Extracted Ranking:</strong>
                  <ol>
                    {completedRankingRows[activeTab].parsed_ranking.map((label, i) => (
                      <li key={i}>
                        {labelToModel && labelToModel[label]
                          ? formatModelLabel(labelToModel[label])
                          : label}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}

          {aggregateRankings && aggregateRankings.length > 0 && (
            <div className="aggregate-rankings">
              <h4>Aggregate Rankings</h4>
              <p className="stage-description">
                Combined results across {voteLabel} — lower average rank is better.
              </p>
              <AggregateRankings aggregateRankings={aggregateRankings} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
