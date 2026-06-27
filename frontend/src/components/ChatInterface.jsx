import { useState, useEffect, useRef, useCallback } from "react";
import { ChevronDown } from "lucide-react";
import Stage1 from "./Stage1";
import Stage2 from "./Stage2";
import Stage3 from "./Stage3";
import CouncilTable from "./CouncilTable";
import WinnerBanner from "./WinnerBanner";
import MarkdownContent from "./MarkdownContent";
import {
  displayModelName,
  estimateCouncilCosts,
  presetNormalCost,
  resolveActiveCouncil,
  shortModelName,
} from "../modelUtils";
import "./ChatInterface.css";

const promptStarters = [
  "Compare the strongest arguments on both sides.",
  "Give me the practical recommendation and caveats.",
  "Stress-test this plan before I act on it.",
];

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
  const modelCountLabel = `${selectedModels.length} model${selectedModels.length === 1 ? "" : "s"} active`;
  const catalogLoaded = (modelMap?.size || 0) > 0;
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
            <h2>{compact ? "Ask the council" : "Start a conversation"}</h2>
            <p>
              {compact
                ? "The active council is ready for the first question."
                : "Choose the first question and the selected models will deliberate."}
            </p>
          </div>
        </div>

        <div
          className="empty-council-summary"
          aria-label="Active council summary"
        >
          <div>
            <span>Active council</span>
            <strong>{active.name}</strong>
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

        <div
          className="empty-model-strip empty-model-strip-full"
          aria-label="Selected models"
        >
          {renderModelChips()}
        </div>

        {compact && (
          <details className="empty-model-disclosure">
            <summary>
              <span>{modelCountLabel}</span>
              <ChevronDown size={16} aria-hidden="true" />
            </summary>
            <div className="empty-model-strip" aria-label="Selected models">
              {renderModelChips()}
            </div>
          </details>
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
          {onOpenModels && (
            <button
              type="button"
              className="adjust-models-btn"
              onClick={onOpenModels}
            >
              Adjust models
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

function OpenRouterSetupSurface({ onOpenIntegrations }) {
  return (
    <div className="openrouter-setup-state">
      <section
        className="openrouter-setup-panel"
        aria-labelledby="openrouter-setup-title"
      >
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
            <h2 id="openrouter-setup-title">
              Add an OpenRouter key to use LLM Council
            </h2>
            <p>
              Google sign-in creates your account. Council runs work after your
              account has its own OpenRouter API key.
            </p>
          </div>
        </div>

        <ol className="openrouter-setup-steps">
          <li>
            Open{" "}
            <a
              href="https://openrouter.ai/settings/keys"
              target="_blank"
              rel="noreferrer"
            >
              OpenRouter API keys
            </a>
            .
          </li>
          <li>Create a key, optionally set a credit limit, then copy it.</li>
          <li>
            Paste it in API &amp; Integrations here. The full key is stored
            server-side and is not shown again.
          </li>
        </ol>

        <div className="openrouter-setup-actions">
          {onOpenIntegrations && (
            <button
              type="button"
              className="start-conversation-btn"
              onClick={onOpenIntegrations}
            >
              Add OpenRouter key
            </button>
          )}
          <a
            className="adjust-models-btn openrouter-docs-link"
            href="https://openrouter.ai/docs/api-reference/authentication"
            target="_blank"
            rel="noreferrer"
          >
            API key docs
          </a>
        </div>
      </section>
    </div>
  );
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  onStopRun,
  onCreateConversation,
  isLoading,
  activeRunId,
  sendError,
  settings,
  onOpenModels,
  onOpenIntegrations,
  openRouterStatus,
  modelMap,
  presets,
}) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);
  const containerRef = useRef(null);
  const textareaRef = useRef(null);
  const shouldAutoScrollRef = useRef(true);
  const hasConfiguredCouncil =
    (settings?.council_models?.length || 0) > 0 && !!settings?.chairman_model;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom < 120;
  };

  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      scrollToBottom();
    }
  }, [conversation]);

  const autoResize = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, []);

  useEffect(() => {
    autoResize();
  }, [input, autoResize]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (openRouterStatus && !openRouterStatus.configured) {
    return (
      <div className="chat-interface">
        <OpenRouterSetupSurface onOpenIntegrations={onOpenIntegrations} />
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="chat-interface">
        <EmptyStartSurface
          settings={settings}
          modelMap={modelMap}
          presets={presets}
          onCreateConversation={onCreateConversation}
          onOpenModels={onOpenModels}
        />
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div
        className="messages-container"
        ref={containerRef}
        onScroll={handleScroll}
      >
        {conversation.messages.length === 0 ? (
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
          conversation.messages.map((msg, index) => (
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

                  {/* Stage 3 — Council Verdict, promoted above the working detail */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Synthesizing final answer…</span>
                    </div>
                  )}
                  {msg.stage3 && (
                    <Stage3
                      hero
                      finalResponse={msg.stage3}
                      costSummary={
                        msg.cost_summary || msg.metadata?.cost_summary
                      }
                      modelMap={modelMap}
                    />
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
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                      stage2Execution={msg.metadata?.stage2_execution}
                      error={msg.error}
                      modelMap={modelMap}
                      defaultCollapsed={!msg.error}
                    />
                  )}

                  {/* Stage 1 — individual responses detail */}
                  {msg.stage1 && (
                    <Stage1 responses={msg.stage1} modelMap={modelMap} defaultCollapsed />
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
                Open API settings
              </button>
            </>
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
              onChange={(e) => setInput(e.target.value)}
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
              </div>
              <div className="input-actions">
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
                    disabled={!input.trim() || isLoading}
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
                    Send
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
