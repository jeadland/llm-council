import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import GearIcon from './GearIcon';
import './ChatInterface.css';

function StageStepper({ msg }) {
  const stages = [
    { key: 'stage1', label: 'Responses', num: 1 },
    { key: 'stage2', label: 'Rankings', num: 2 },
    { key: 'stage3', label: 'Synthesis', num: 3 },
  ];

  const getStatus = (key) => {
    if (msg[key]) return 'complete';
    if (msg.loading?.[key]) return 'active';
    return 'pending';
  };

  return (
    <div className="stage-stepper">
      {stages.map((stage, i) => {
        const status = getStatus(stage.key);
        return (
          <div key={stage.key} className="stepper-segment">
            <div className={`stepper-node ${status}`}>
              {status === 'complete' ? (
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                  <path d="M3 8.5L6.5 12L13 4" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              ) : status === 'active' ? (
                <div className="stepper-pulse" />
              ) : (
                <span>{stage.num}</span>
              )}
            </div>
            <span className={`stepper-label ${status}`}>{stage.label}</span>
            {i < stages.length - 1 && (
              <div className={`stepper-connector ${status === 'complete' ? 'complete' : ''}`} />
            )}
          </div>
        );
      })}
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
  settings,
  onOpenSettings,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const containerRef = useRef(null);
  const textareaRef = useRef(null);
  const shouldAutoScrollRef = useRef(true);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  }, []);

  useEffect(() => {
    autoResize();
  }, [input, autoResize]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <img
            src="/images/llm-council-icon.svg"
            alt="LLM Council"
            className="empty-state-logo"
            width="64"
            height="64"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
          <button className="start-conversation-btn" onClick={onCreateConversation}>
            Start a conversation
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="messages-container" ref={containerRef} onScroll={handleScroll}>
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">LLM Council</div>

                  {/* Progress Stepper — show while any stage is loading */}
                  {(msg.loading?.stage1 || msg.loading?.stage2 || msg.loading?.stage3) && (
                    <StageStepper msg={msg} />
                  )}

                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Collecting individual responses…</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} defaultCollapsed />}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Peer rankings in progress…</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                      defaultCollapsed
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Synthesizing final answer…</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}

                  {/* Error state — run failed before completing */}
                  {msg.error && !msg.stage3 && !msg.loading?.stage3 && (
                    <div className="stage stage3 stage3-fallback">
                      <div className="stage3-header">
                        <div className="stage3-icon">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="15" y1="9" x2="9" y2="15"/>
                            <line x1="9" y1="9" x2="15" y2="15"/>
                          </svg>
                        </div>
                        <div>
                          <h3 className="stage-title">Council Error</h3>
                          <div className="chairman-label">Synthesis could not be completed</div>
                        </div>
                      </div>
                      <div className="final-response">
                        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
                          The council encountered an error during synthesis. Please try again.
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

      <form className="input-form" onSubmit={handleSubmit}>
        <div className="input-form-inner">
          <div className={`input-card${isLoading ? ' is-loading' : ''}`}>
            <textarea
              ref={textareaRef}
              className="message-input"
              placeholder={isLoading ? 'Council is thinking…' : 'Ask the council anything…'}
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
                  <kbd>Enter</kbd> send &nbsp;·&nbsp; <kbd>Shift+Enter</kbd> newline
                </span>
                {input.length > 0 && (
                  <span
                    className={`input-char-count${input.length > 3800 ? ' at-limit' : input.length > 3000 ? ' near-limit' : ''}`}
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
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                      <rect x="3" y="3" width="10" height="10" rx="2"/>
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
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/>
                    </svg>
                    Send
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </form>

      {/* Onboarding hint — always visible, more prominent when no models configured */}
      {(() => {
        const hasModels = settings?.council_models?.length > 0;
        const hasChairman = !!settings?.chairman_model;
        const isUnconfigured = !hasModels || !hasChairman;
        return (
          <div className={`onboarding-hint${isUnconfigured ? ' onboarding-hint--warn' : ''}`}>
            {isUnconfigured ? (
              <>
                {onOpenSettings ? (
                  <button
                    type="button"
                    className="onboarding-hint-gear-btn"
                    onClick={onOpenSettings}
                    aria-label="Open settings"
                    title="Open settings"
                  >
                    <GearIcon size={16} aria-hidden="true" />
                  </button>
                ) : (
                  <GearIcon size={16} aria-hidden="true" className="onboarding-hint-icon" />
                )}
                Select council models and chairman in{' '}
                {onOpenSettings ? (
                  <button
                    type="button"
                    className="onboarding-hint-settings-link"
                    onClick={onOpenSettings}
                  >
                    Settings
                  </button>
                ) : (
                  <strong>Settings</strong>
                )}{' '}
                to get started.
              </>
            ) : (
              <>
                {onOpenSettings ? (
                  <button
                    type="button"
                    className="onboarding-hint-gear-btn"
                    onClick={onOpenSettings}
                    aria-label="Open settings"
                    title="Open settings"
                  >
                    <GearIcon size={16} aria-hidden="true" />
                  </button>
                ) : (
                  <GearIcon size={16} aria-hidden="true" className="onboarding-hint-icon" />
                )}
                {settings.council_models.length} council model{settings.council_models.length !== 1 ? 's' : ''} active · Chairman:{' '}
                <strong>{settings.chairman_model.split('/').pop()}</strong>
                {' · '}
                {onOpenSettings ? (
                  <button
                    type="button"
                    className="onboarding-hint-settings-link"
                    onClick={onOpenSettings}
                  >
                    Adjust in Settings
                  </button>
                ) : (
                  <>Adjust in ⚙️ Settings</>
                )}
              </>
            )}
          </div>
        );
      })()}
    </div>
  );
}
