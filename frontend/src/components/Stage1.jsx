import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import MarkdownContent from './MarkdownContent';
import { resolveModelLabel } from '../modelUtils';
import {
  ModelReviewerTabs,
  ReviewerContentHeader,
  StageIntro,
} from './StagePanels';
import './StagePanels.css';
import './Stage1.css';

function hitOutputLimit(response) {
  const costCall = response?.cost_call || {};
  const finishReason = String(costCall.finish_reason || '').toLowerCase();
  const nativeFinishReason = String(costCall.native_finish_reason || '').toLowerCase();
  return [finishReason, nativeFinishReason].some((reason) =>
    ['length', 'max_tokens', 'max_output_tokens'].includes(reason)
  );
}

export default function Stage1({
  responses,
  modelMap,
  defaultCollapsed = false,
  expandToken = 0,
}) {
  const [activeTab, setActiveTab] = useState(0);
  const [collapsed, setCollapsed] = useState(defaultCollapsed && !expandToken);

  if (!responses || responses.length === 0) {
    return null;
  }

  const summary =
    responses.length === 1
      ? `${resolveModelLabel(responses[0].model, modelMap)} responded`
      : `${responses.length} model responses`;

  const tabItems = responses.map((resp) => ({ model: resp.model }));
  const active = responses[activeTab];

  return (
    <div className="stage stage1">
      <button
        type="button"
        className={`collapse-toggle${collapsed ? '' : ' collapse-toggle--sticky'}`}
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
          <StageIntro title="Before peer review">
            Each council model answered independently. Compare how different models approached the
            same question.
          </StageIntro>

          <ModelReviewerTabs
            items={tabItems}
            activeIndex={activeTab}
            onChange={setActiveTab}
            idPrefix="stage1"
            ariaLabel="Select model response"
            modelMap={modelMap}
          />

          <div
            className="stage-tab-panel"
            role="tabpanel"
            id={`stage1-panel-${activeTab}`}
            aria-labelledby={`stage1-tab-${activeTab}`}
          >
            <ReviewerContentHeader
              model={active.model}
              subtitle="Individual answer"
              modelMap={modelMap}
            />
            {hitOutputLimit(active) && (
              <div className="stage1-limit-alert" role="status">
                This model reached the output limit, so its individual answer may be incomplete.
              </div>
            )}
            <MarkdownContent className="response-text">
              {active.response}
            </MarkdownContent>
          </div>
        </>
      )}
    </div>
  );
}
