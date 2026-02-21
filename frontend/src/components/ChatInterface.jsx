import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
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
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            className="message-input"
            placeholder="Ask the council anything…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={1}
          />
          <span className="input-hint">
            <kbd>Enter</kbd> send · <kbd>Shift+Enter</kbd> newline
          </span>
        </div>
        <div className="input-actions">
          <button
            type="submit"
            className="send-button"
            disabled={!input.trim() || isLoading}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 2L11 13" /><path d="M22 2L15 22L11 13L2 9L22 2Z" />
            </svg>
            <span>Send</span>
          </button>
          {isLoading && activeRunId && (
            <button
              type="button"
              className="stop-button"
              onClick={onStopRun}
            >
              Stop
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
