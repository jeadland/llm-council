import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import MarkdownContent from './MarkdownContent';
import AggregateRankings from './AggregateRankings';
import { resolveModelLabel } from '../modelUtils';
import {
  ModelReviewerTabs,
  ReviewerContentHeader,
  StageIntro,
} from './StagePanels';
import './StagePanels.css';
import './Stage2.css';

function deAnonymizeText(text, labelToModel, modelMap) {
  if (!labelToModel) return text;

  let result = text;
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = resolveModelLabel(model, modelMap);
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
  modelMap,
  defaultCollapsed = false,
  expandToken = 0,
}) {
  const [activeTab, setActiveTab] = useState(0);
  const [collapsed, setCollapsed] = useState(defaultCollapsed && !expandToken);
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
    ? `${isPartial ? 'Partial · ' : ''}Top: ${resolveModelLabel(topAggregate.model, modelMap)} · ${topAggregate.average_rank.toFixed(2)} avg`
    : `${isPartial ? 'Partial · ' : ''}${voteLabel}`;

  const tabItems = completedRankingRows.map((row) => ({
    model: row.model,
    invalid: row.ranking_valid === false,
  }));
  const activeRow = completedRankingRows[activeTab];

  return (
    <div className="stage stage2">
      <button
        type="button"
        className={`collapse-toggle${collapsed ? '' : ' collapse-toggle--sticky'}`}
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
          <StageIntro title="Anonymous peer review">
            Each model scored every answer using anonymous labels (Response A, B, C…). Names shown
            in <strong>bold</strong> below are for readability — the original review used anonymous
            labels only.
          </StageIntro>

          {isPartial && (
            <div className="stage2-partial-alert" role="status">
              <strong>Partial peer review:</strong> this run received {voteLabel}.{' '}
              {missingModels.length > 0 && (
                <span>
                  Missing: {missingModels.map((model) => resolveModelLabel(model, modelMap)).join(', ')}.
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
                      {resolveModelLabel(model, modelMap)} {attemptsByModel[model] || 0}/{maxAttempts}
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
                        <strong>{resolveModelLabel(model, modelMap)}:</strong>{' '}
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

          {completedRankingRows.length > 0 && (
            <>
              <ModelReviewerTabs
                items={tabItems}
                activeIndex={activeTab}
                onChange={setActiveTab}
                idPrefix="stage2"
                ariaLabel="Select peer evaluation"
                modelMap={modelMap}
              />

              <div
                className="stage-tab-panel"
                role="tabpanel"
                id={`stage2-panel-${activeTab}`}
                aria-labelledby={`stage2-tab-${activeTab}`}
              >
                <ReviewerContentHeader
                  model={activeRow.model}
                  subtitle="Peer evaluation"
                  modelMap={modelMap}
                />
                {activeRow.ranking_valid === false && (
                  <div className="stage2-invalid-alert" role="status">
                    This peer review returned an invalid ranking and was not counted in aggregate scoring.
                    {activeRow.ranking_issues?.length > 0 && (
                      <div className="stage2-diagnostic-list">
                        {activeRow.ranking_issues.map((issue) => (
                          <div key={issue} className="stage2-diagnostic-row">{issue}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                <MarkdownContent className="ranking-content">
                  {deAnonymizeText(activeRow.ranking, labelToModel, modelMap)}
                </MarkdownContent>

                {activeRow.parsed_ranking?.length > 0 && (
                  <div className="parsed-ranking">
                    <strong>Extracted ranking</strong>
                    <ol>
                      {activeRow.parsed_ranking.map((label, i) => (
                        <li key={i}>
                          {labelToModel && labelToModel[label]
                            ? resolveModelLabel(labelToModel[label], modelMap)
                            : label}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            </>
          )}

          {aggregateRankings && aggregateRankings.length > 0 && (
            <div className="aggregate-rankings">
              <StageIntro title="Combined scoreboard" variant="subtle">
                Results across {voteLabel}. Lower average rank is better.
              </StageIntro>
              <AggregateRankings aggregateRankings={aggregateRankings} modelMap={modelMap} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
