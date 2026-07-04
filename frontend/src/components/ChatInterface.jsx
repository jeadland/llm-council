import { useState, useEffect, useRef, useCallback } from "react";
import { Sparkles, Undo2, Loader2 } from "lucide-react";
import { api } from "../api";
import Stage1 from "./Stage1";
import Stage2 from "./Stage2";
import Stage3 from "./Stage3";
import CouncilTable from "./CouncilTable";
import WinnerBanner from "./WinnerBanner";
import MarkdownContent from "./MarkdownContent";
import CouncilProcessSteps from "./CouncilProcessSteps";
import {
  abbreviateModelName,
  displayModelName,
  estimateCouncilCosts,
  presetNormalCost,
  resolveActiveCouncil,
  resolveManagedProfileSlug,
  shortModelName,
} from "../modelUtils";
import ProviderAvatar from "./ProviderAvatar";
import "./ChatInterface.css";

const promptStarters = [
  "Compare the strongest arguments on both sides.",
  "Give me the practical recommendation and caveats.",
  "Stress-test this plan before I act on it.",
];

function processStatesFromMessage(msg) {
  const error = Boolean(msg?.error);
  return {
    stage1: msg?.stage1
      ? "complete"
      : msg?.loading?.stage1
        ? "active"
        : error
          ? "error"
          : "pending",
    stage2: msg?.stage2
      ? "complete"
      : msg?.loading?.stage2
        ? "active"
        : error && msg?.stage1
          ? "error"
          : "pending",
    stage3: msg?.stage3
      ? "complete"
      : msg?.loading?.stage3
        ? "active"
        : error && !msg?.stage3
          ? "error"
          : "pending",
  };
}

function shouldShowProcessSteps(msg) {
  return Boolean(
    msg?.loading?.stage1 ||
      msg?.loading?.stage2 ||
      msg?.loading?.stage3 ||
      msg?.stage1 ||
      msg?.stage2 ||
      msg?.stage3 ||
      msg?.error,
  );
}

function voteLabelFromExecution(stage2Execution, aggregateRankings) {
  const expected = Number(
    stage2Execution?.expected_rankings_count || aggregateRankings?.length || 0,
  );
  const completed = Number(
    stage2Execution?.completed_rankings_count ?? aggregateRankings?.length ?? 0,
  );
  if (!expected) return "";
  return `${completed} of ${expected} vote${expected === 1 ? "" : "s"}`;
}

function EmptyStartSurface({
  compact = false,
  settings,
  modelMap,
  presets,
  onCreateConversation,
  onOpenModels,
  onUseStarter,
}) {
  const selectedModels = settings?.council_models || [];
  const chairman = settings?.chairman_model || "";
  const active = resolveActiveCouncil(settings, presets);
  const fallbackEstimate = estimateCouncilCosts(
    selectedModels,
    chairman,
    modelMap,
  );
  const presetEstimate = active.selectionMatchesPreset
    ? presetNormalCost(active.preset)
    : null;
  const estimate =
    presetEstimate || fallbackEstimate?.display || "Pricing unavailable";
  const catalogLoaded = (modelMap?.size || 0) > 0;
  const hasConfiguredCouncil = selectedModels.length > 0 && !!chairman;
  const renderModelChips = () =>
    selectedModels.length > 0 ? (
      selectedModels.map((modelId) => (
        <span
          className={`empty-model-chip${catalogLoaded && !modelMap.has(modelId) ? " empty-model-chip-muted" : ""}`}
          key={modelId}
        >
          {displayModelName(modelId, modelMap).replace(/^.*?:\s*/, "")}
        </span>
      ))
    ) : (
      <span className="empty-model-empty">No council models selected</span>
    );

  return (
    <div
      className={`empty-state empty-state-start${compact ? " empty-state-start--compact" : ""}`}
    >
      <div className="empty-state-panel">
        <div className="empty-state-heading-row">
          <img
            src={`${import.meta.env.BASE_URL}images/llm-council-icon.svg`}
            alt="LLM Council"
            className="empty-state-logo"
            width="46"
            height="46"
            onError={(e) => {
              e.target.style.display = "none";
            }}
          />
          <div>
            <h2>What's on your mind?</h2>
            <p>
              {compact
                ? "Ask a question and the council will deliberate."
                : "Start with the question you want the council to work through."}
            </p>
          </div>
        </div>

        <div
          className="empty-council-summary"
          aria-label="Active council summary"
        >
          <div className="empty-council-summary-council">
            <span>Active council</span>
            <strong>{active.name}</strong>
            {selectedModels.length > 0 ? (
              <ul className="empty-council-model-list" aria-label="Council models">
                {selectedModels.map((modelId) => (
                  <li className="empty-council-model-item" key={modelId}>
                    <ProviderAvatar
                      className="empty-council-model-avatar"
                      modelId={modelId}
                      aria-hidden="true"
                    />
                    <span title={displayModelName(modelId, modelMap)}>
                      {abbreviateModelName(modelId, modelMap) || shortModelName(modelId)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-council-model-empty">No council models selected</p>
            )}
          </div>
          <div>
            <span>Chairman</span>
            <strong>{shortModelName(chairman) || "None"}</strong>
          </div>
          <div>
            <span>Est. cost</span>
            <strong>{estimate}</strong>
          </div>
        </div>

        {!compact && (
          <div
            className="empty-model-strip empty-model-strip-full"
            aria-label="Selected models"
          >
            {renderModelChips()}
          </div>
        )}

        {!compact && hasConfiguredCouncil && (
          <CouncilProcessSteps
            variant="static"
            title="How your council deliberates"
          />
        )}

        <div className="empty-state-actions">
          {!compact && (
            <button
              type="button"
              className="start-conversation-btn"
              onClick={onCreateConversation}
            >
              Start a conversation
            </button>
          )}
          {!compact && onOpenModels && (
            <button
              type="button"
              className="adjust-models-btn"
              onClick={onOpenModels}
            >
              Council setup
            </button>
          )}
        </div>

        {compact && onUseStarter && (
          <div className="prompt-starters" aria-label="Prompt starters">
            {promptStarters.map((starter) => (
              <button
                type="button"
                key={starter}
                onClick={() => onUseStarter(starter)}
              >
                {starter}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  onStopRun,
  isLoading,
  activeRunId,
  sendError,
  settings,
  onOpenModels,
  onOpenIntegrations,
  openRouterStatus,
  billingStatus,
  councilProfiles,
  modelMap,
  presets,
}) {
  const [input, setInput] = useState("");
  const [isImproving, setIsImproving] = useState(false);
  const [isEstimating, setIsEstimating] = useState(false);
  const selectedProfileSlug = resolveManagedProfileSlug(settings, presets, councilProfiles);
  const [pendingEstimate, setPendingEstimate] = useState(null);
  const [preImproveInput, setPreImproveInput] = useState(null);
  const [improveError, setImproveError] = useState("");
  const [accessGuardMessage, setAccessGuardMessage] = useState("");
  const [stageExpandRequest, setStageExpandRequest] = useState({
    messageIndex: null,
    stage: null,
    token: 0,
  });
  const messagesEndRef = useRef(null);
  const containerRef = useRef(null);
  const textareaRef = useRef(null);
  const shouldAutoScrollRef = useRef(true);
  const conversationIdRef = useRef(null);
  const hasConfiguredCouncil =
    (settings?.council_models?.length || 0) > 0 && !!settings?.chairman_model;
  const managedReady =
    billingStatus?.billing_mode === "managed" &&
    billingStatus?.managed_mode_enabled;
  const needsModelAccess = Boolean(
    openRouterStatus && !openRouterStatus.configured && !managedReady,
  );
  const messages = conversation?.messages || [];

  const scrollToBottom = useCallback((behavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior, block: "end" });
  }, []);

  const scrollToLatestVerdict = useCallback((behavior = "auto") => {
    const container = containerRef.current;
    if (!container) return;

    const msgs = conversation?.messages || [];
    let anchorId = null;
    for (let i = msgs.length - 1; i >= 0; i -= 1) {
      const msg = msgs[i];
      if (msg.role !== "assistant") continue;
      if (msg.stage3 || msg.loading?.stage3) {
        anchorId = `${i}-stage3`;
        break;
      }
    }

    if (anchorId) {
      const target = container.querySelector(
        `[data-stage-anchor="${anchorId}"]`,
      );
      if (target) {
        target.scrollIntoView({ behavior, block: "start" });
        return;
      }
    }

    scrollToBottom(behavior);
  }, [conversation?.messages, scrollToBottom]);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom < 120;
  };

  const handleStageStepClick = useCallback((messageIndex, stage) => {
    shouldAutoScrollRef.current = false;
    setStageExpandRequest((prev) => ({
      messageIndex,
      stage,
      token: prev.token + 1,
    }));
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const target = containerRef.current?.querySelector(
          `[data-stage-anchor="${messageIndex}-${stage}"]`,
        );
        target?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }, []);

  useEffect(() => {
    const id = conversation?.id;
    if (!id) {
      conversationIdRef.current = null;
      return;
    }

    const switched = id !== conversationIdRef.current;
    if (switched) {
      conversationIdRef.current = id;
      shouldAutoScrollRef.current = true;
    }

    if (!shouldAutoScrollRef.current) return;

    const behavior = switched ? "auto" : "smooth";
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        scrollToLatestVerdict(behavior);
      });
    });
  }, [conversation?.id, conversation?.messages, scrollToLatestVerdict]);

  const autoResize = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, []);

  useEffect(() => {
    autoResize();
  }, [input, autoResize]);

  const submitNow = (content, options = {}) => {
    onSendMessage(content, options);
    setInput("");
    setPreImproveInput(null);
    setImproveError("");
    setAccessGuardMessage("");
    setPendingEstimate(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading || isImproving) return;
    if (needsModelAccess) {
      setAccessGuardMessage(
        "Add an OpenRouter key in model access before running the council.",
      );
      return;
    }
    if (!managedReady) {
      submitNow(input);
      return;
    }
    setIsEstimating(true);
    setImproveError("");
    try {
      const estimate = await api.estimateCouncilProfile({
        content: input,
        profileSlug: selectedProfileSlug,
      });
      setPendingEstimate({ content: input, estimate });
    } catch (err) {
      setImproveError(err?.message || "Could not estimate managed run.");
    } finally {
      setIsEstimating(false);
    }
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
    if (preImproveInput !== null) setPreImproveInput(null);
    if (improveError) setImproveError("");
    if (accessGuardMessage) setAccessGuardMessage("");
  };

  const handleImprove = async () => {
    if (!input.trim() || isLoading || isImproving) return;
    const original = input;
    setImproveError("");
    setIsImproving(true);
    try {
      const { improved } = await api.improvePrompt(original);
      if (improved && improved.trim() && improved.trim() !== original.trim()) {
        setPreImproveInput(original);
        setInput(improved);
        requestAnimationFrame(autoResize);
      } else {
        setImproveError("No changes suggested.");
      }
    } catch (err) {
      setImproveError(err?.message || "Couldn't improve the question.");
    } finally {
      setIsImproving(false);
    }
  };

  const handleUndoImprove = () => {
    if (preImproveInput !== null) {
      setInput(preImproveInput);
      setPreImproveInput(null);
      setImproveError("");
      requestAnimationFrame(autoResize);
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="chat-interface">
      <div
        className="messages-container"
        ref={containerRef}
        onScroll={handleScroll}
      >
        {messages.length === 0 ? (
          <EmptyStartSurface
            compact
            settings={settings}
            modelMap={modelMap}
            presets={presets}
            onOpenModels={onOpenModels}
            onUseStarter={(starter) => {
              setInput(starter);
              requestAnimationFrame(() => {
                textareaRef.current?.focus();
                autoResize();
              });
            }}
          />
        ) : (
          messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === "user" ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <MarkdownContent>{msg.content}</MarkdownContent>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">LLM Council</div>

                  {/* Live council table — per-model agent progress and drill-down */}
                  <CouncilTable
                    msg={msg}
                    modelMap={modelMap}
                    fallbackModels={settings?.council_models || []}
                  />

                  {shouldShowProcessSteps(msg) && (
                    <CouncilProcessSteps
                      states={processStatesFromMessage(msg)}
                      onStepClick={(stage) => handleStageStepClick(index, stage)}
                    />
                  )}

                  {/* Stage 3 — Council Verdict, promoted above the working detail */}
                  {msg.loading?.stage3 && (
                    <div
                      className="stage-loading"
                      data-stage-anchor={`${index}-stage3`}
                    >
                      <div className="spinner"></div>
                      <span>Synthesizing final answer…</span>
                    </div>
                  )}
                  {msg.stage3 && (
                    <div data-stage-anchor={`${index}-stage3`}>
                      <Stage3
                        hero
                        finalResponse={msg.stage3}
                        costSummary={
                          msg.cost_summary || msg.metadata?.cost_summary
                        }
                        billingReceipt={
                          msg.billing_receipt || msg.metadata?.billing_receipt
                        }
                        modelMap={modelMap}
                      />
                    </div>
                  )}

                  {/* Winner banner — easy-to-find result with expandable scoreboard */}
                  {!msg.loading?.stage2 &&
                    msg.metadata?.aggregate_rankings?.length > 0 && (
                      <WinnerBanner
                        aggregateRankings={msg.metadata.aggregate_rankings}
                        voteLabel={voteLabelFromExecution(
                          msg.metadata?.stage2_execution,
                          msg.metadata.aggregate_rankings,
                        )}
                        modelMap={modelMap}
                      />
                    )}

                  {/* Stage 2 — peer rankings (the "show the work") */}
                  {msg.stage2 && (
                    <div data-stage-anchor={`${index}-stage2`}>
                      <Stage2
                        key={`stage2-${index}-${
                          stageExpandRequest.messageIndex === index &&
                          stageExpandRequest.stage === "stage2"
                            ? stageExpandRequest.token
                            : 0
                        }`}
                        rankings={msg.stage2}
                        labelToModel={msg.metadata?.label_to_model}
                        aggregateRankings={msg.metadata?.aggregate_rankings}
                        stage2Execution={msg.metadata?.stage2_execution}
                        error={msg.error}
                        modelMap={modelMap}
                        defaultCollapsed={!msg.error}
                        expandToken={
                          stageExpandRequest.messageIndex === index &&
                          stageExpandRequest.stage === "stage2"
                            ? stageExpandRequest.token
                            : 0
                        }
                      />
                    </div>
                  )}

                  {/* Stage 1 — individual responses detail */}
                  {msg.stage1 && (
                    <div data-stage-anchor={`${index}-stage1`}>
                      <Stage1
                        key={`stage1-${index}-${
                          stageExpandRequest.messageIndex === index &&
                          stageExpandRequest.stage === "stage1"
                            ? stageExpandRequest.token
                            : 0
                        }`}
                        responses={msg.stage1}
                        modelMap={modelMap}
                        defaultCollapsed
                        expandToken={
                          stageExpandRequest.messageIndex === index &&
                          stageExpandRequest.stage === "stage1"
                            ? stageExpandRequest.token
                            : 0
                        }
                      />
                    </div>
                  )}

                  {/* Error state — run failed before completing */}
                  {msg.error && !msg.stage3 && !msg.loading?.stage3 && (
                    <div className="stage stage3 stage3-fallback">
                      <div className="stage3-header">
                        <div className="stage3-icon">
                          <svg
                            width="20"
                            height="20"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <circle cx="12" cy="12" r="10" />
                            <line x1="15" y1="9" x2="9" y2="15" />
                            <line x1="9" y1="9" x2="15" y2="15" />
                          </svg>
                        </div>
                        <div>
                          <h3 className="stage-title">Council Error</h3>
                          <div className="chairman-label">
                            Synthesis could not be completed
                          </div>
                        </div>
                      </div>
                      <div className="final-response">
                        <p
                          style={{ color: "var(--text-secondary)", margin: 0 }}
                        >
                          The council encountered an error during synthesis.
                          Please try again.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {sendError && (
        <div className="send-error" role="alert">
          {sendError}
          {sendError.includes("OpenRouter") && onOpenIntegrations && (
            <>
              {" "}
              <button
                type="button"
                className="onboarding-hint-settings-link"
                onClick={onOpenIntegrations}
              >
                Open model access
              </button>
            </>
          )}
        </div>
      )}

      {accessGuardMessage && (
        <div className="onboarding-hint onboarding-hint--warn" role="alert">
          {accessGuardMessage}{" "}
          {onOpenIntegrations && (
            <button
              type="button"
              className="onboarding-hint-settings-link"
              onClick={() => {
                setAccessGuardMessage("");
                onOpenIntegrations();
              }}
            >
              Open model access
            </button>
          )}
        </div>
      )}

      {!hasConfiguredCouncil && (
        <div className="onboarding-hint onboarding-hint--warn">
          Select council models and chairman in{" "}
          {onOpenModels ? (
            <button
              type="button"
              className="onboarding-hint-settings-link"
              onClick={onOpenModels}
            >
              Models
            </button>
          ) : (
            <strong>Models</strong>
          )}{" "}
          to get started.
        </div>
      )}

      <form className="input-form" onSubmit={handleSubmit}>
        <div className="input-form-inner">
          <div className={`input-card${isLoading ? " is-loading" : ""}`}>
            <textarea
              ref={textareaRef}
              className="message-input"
              placeholder={
                isLoading ? "Council is thinking…" : "Ask the council anything…"
              }
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              rows={1}
              aria-label="Message input"
            />
            <div className="input-bottom-row">
              <div className="input-bottom-left">
                <span className="input-hint" aria-hidden="true">
                  <kbd>Enter</kbd> send &nbsp;·&nbsp; <kbd>Shift+Enter</kbd>{" "}
                  newline
                </span>
                {input.length > 0 && (
                  <span
                    className={`input-char-count${input.length > 3800 ? " at-limit" : input.length > 3000 ? " near-limit" : ""}`}
                    aria-live="polite"
                    aria-label={`${input.length} characters`}
                  >
                    {input.length}
                  </span>
                )}
                {improveError && (
                  <span className="improve-error" role="status" aria-live="polite">
                    {improveError}
                  </span>
                )}
              </div>
              <div className="input-actions">
                {!isLoading && (
                  <button
                    type="button"
                    className="improve-button"
                    onClick={handleImprove}
                    disabled={!input.trim() || isImproving}
                    title="Rewrite your prompt for clarity before sending."
                    aria-label="Improve my question with AI"
                  >
                    {isImproving ? (
                      <Loader2 size={15} className="improve-spinner" aria-hidden="true" />
                    ) : (
                      <Sparkles size={15} aria-hidden="true" />
                    )}
                    {isImproving ? "Improving…" : "Improve"}
                  </button>
                )}
                {!isLoading && preImproveInput !== null && (
                  <button
                    type="button"
                    className="undo-improve"
                    onClick={handleUndoImprove}
                    title="Restore your original question"
                    aria-label="Undo AI edit"
                  >
                    <Undo2 size={15} aria-hidden="true" />
                    Undo
                  </button>
                )}
                {isLoading && activeRunId ? (
                  <button
                    type="button"
                    className="stop-button"
                    onClick={onStopRun}
                    aria-label="Stop generation"
                  >
                    {/* Stop icon */}
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 16 16"
                      fill="currentColor"
                      aria-hidden="true"
                    >
                      <rect x="3" y="3" width="10" height="10" rx="2" />
                    </svg>
                    Stop
                  </button>
                ) : (
                  <button
                    type="submit"
                    className="send-button"
                    disabled={!input.trim() || isLoading || isEstimating}
                    aria-label="Send message"
                  >
                    {/* Paper-plane icon */}
                    <svg
                      width="15"
                      height="15"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M22 2L11 13" />
                      <path d="M22 2L15 22L11 13L2 9L22 2Z" />
                    </svg>
                    {isEstimating ? (
                      <span>...</span>
                    ) : (
                      <>
                        <span>Send</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </form>

      {pendingEstimate && (
        <div className="estimate-modal-backdrop" role="presentation">
          <div className="estimate-modal" role="dialog" aria-modal="true" aria-labelledby="estimate-title">
            <div className="estimate-modal-header">
              <div>
                <h3 id="estimate-title">
                  {pendingEstimate.estimate.profile?.display_name || "Managed Council"}
                </h3>
                <p>{pendingEstimate.estimate.profile?.best_for}</p>
              </div>
              <button
                type="button"
                className="estimate-close-btn"
                onClick={() => setPendingEstimate(null)}
                aria-label="Close estimate"
              >
                Close
              </button>
            </div>
            <div className="estimate-grid">
              <div>
                <span>Estimated cost</span>
                <strong>
                  ${Number(pendingEstimate.estimate.estimated_app_cost_low_usd || 0).toFixed(2)}
                  -
                  ${Number(pendingEstimate.estimate.estimated_app_cost_high_usd || 0).toFixed(2)}
                </strong>
              </div>
              <div>
                <span>Maximum charge</span>
                <strong>${Number(pendingEstimate.estimate.max_app_charge_usd || 0).toFixed(2)}</strong>
              </div>
              <div>
                <span>Your balance</span>
                <strong>${Number(billingStatus?.available_balance_usd || 0).toFixed(2)}</strong>
              </div>
            </div>
            <p className="estimate-copy">
              Cost includes model usage, routing, storage, and service fee. You are charged after the run for completed usage, up to the maximum charge.
            </p>
            {!pendingEstimate.estimate.can_run && (
              <div className="estimate-warning">
                Your balance is too low for this counsel profile. Add balance or switch to your own OpenRouter key.
              </div>
            )}
            <div className="estimate-actions">
              <button type="button" className="adjust-models-btn" onClick={() => setPendingEstimate(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="start-conversation-btn"
                disabled={!pendingEstimate.estimate.can_run}
                onClick={() =>
                  submitNow(pendingEstimate.content, {
                    billingMode: "managed",
                    profileSlug: pendingEstimate.estimate.profile?.slug || selectedProfileSlug,
                  })
                }
              >
                Run Council
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
