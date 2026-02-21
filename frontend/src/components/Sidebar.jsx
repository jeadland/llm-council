import { useState, useEffect } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onTogglePin,
  onDeleteConversation,
  settings,
  onSaveSettings,
  isOpen,
  openSettingsOnOpen,
  onSettingsOpened,
}) {
  const [showSettings, setShowSettings] = useState(false);

  // When mobile topbar gear is tapped: sidebar opens + settings should auto-open
  useEffect(() => {
    if (isOpen && openSettingsOnOpen && !showSettings) {
      openSettings();
      onSettingsOpened?.();
    }
  }, [isOpen, openSettingsOnOpen]); // eslint-disable-line react-hooks/exhaustive-deps
  const [draftCouncil, setDraftCouncil] = useState(settings?.council_models || []);
  const [draftChairman, setDraftChairman] = useState(settings?.chairman_model || '');
  const [draftThemeMode, setDraftThemeMode] = useState(settings?.theme_mode || 'system');
  // Accordion state for chairman picker
  const [chairmanExpanded, setChairmanExpanded] = useState(false);
  // Accordion state for council models (collapsed = only selected; expanded = all)
  const [councilExpanded, setCouncilExpanded] = useState(false);

  const available = settings?.available_models || [];

  const openSettings = () => {
    setDraftCouncil(settings?.council_models || []);
    setDraftChairman(settings?.chairman_model || '');
    setDraftThemeMode(settings?.theme_mode || 'system');
    setChairmanExpanded(false);
    setCouncilExpanded(false);
    setShowSettings(true);
  };

  const closeSettings = () => {
    setChairmanExpanded(false);
    setCouncilExpanded(false);
    setShowSettings(false);
  };

  const toggleModel = (model) => {
    setDraftCouncil((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model]
    );
  };

  const selectChairman = (model) => {
    setDraftChairman(model);
    setChairmanExpanded(false); // collapse after selection
  };

  const save = async () => {
    const safeCouncil = draftCouncil.length ? draftCouncil : settings?.council_models || [];
    const safeChairman = draftChairman || settings?.chairman_model;
    await onSaveSettings({
      council_models: safeCouncil,
      chairman_model: safeChairman,
      theme_mode: draftThemeMode,
    });
    setShowSettings(false);
    setChairmanExpanded(false);
  };

  const currentChairman = settings?.chairman_model || '';
  const chairmanShort = currentChairman ? currentChairman.split('/').pop() : '';
  const draftChairmanShort = draftChairman ? draftChairman.split('/').pop() : '';

  return (
    <div className={`sidebar ${isOpen ? 'open' : ''} ${showSettings ? 'settings-fullpanel' : ''}`}>

      {/* ── Full-panel settings mode ── */}
      {showSettings && (
        <div className="settings-fullpanel-content">
          {/* Settings header row */}
          <div className="settings-fullpanel-header">
            <button
              className="settings-back-btn"
              onClick={closeSettings}
              aria-label="Back to conversations"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M10 3L5 8L10 13" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <span className="settings-fullpanel-title">Settings</span>
            {/* Static pencil/edit icon — replaces spinning gear */}
            <div className="settings-fullpanel-editicon" aria-hidden="true">
              <svg width="17" height="17" viewBox="0 0 20 20" fill="none">
                <path
                  d="M14.5 2.5a2.121 2.121 0 0 1 3 3L6.5 16.5l-4 1 1-4L14.5 2.5Z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              </svg>
            </div>
          </div>

          {/* Settings body — scrollable */}
          <div className="settings-fullpanel-body">
            <div className="settings-subtitle">Council Models</div>
            {available.length === 0 && (
              <p className="settings-empty-note">No models available. Check your OpenClaw model library.</p>
            )}

            {/* ── Council models collapsible accordion ── */}
            {available.length > 0 && (() => {
              // Models to render: collapsed → only selected; expanded → all
              const unselected = available.filter((m) => !draftCouncil.includes(m));
              const modelsToShow = councilExpanded ? available : available.filter((m) => draftCouncil.includes(m));
              const extraCount = unselected.length;

              return (
                <div className="council-models-accordion">
                  {/* Render rows */}
                  <div className="council-models-list">
                    {modelsToShow.length === 0 && !councilExpanded && (
                      <p className="settings-empty-note council-models-empty">
                        No models selected. Expand to add some.
                      </p>
                    )}
                    {modelsToShow.map((model) => {
                      const checked = draftCouncil.includes(model);
                      const shortName = model.split('/').pop();
                      return (
                        <button
                          key={model}
                          type="button"
                          role="checkbox"
                          aria-checked={checked}
                          className={`council-model-row${checked ? ' checked' : ''}`}
                          onClick={() => toggleModel(model)}
                        >
                          <span className="council-model-checkbox" aria-hidden="true">
                            {checked && (
                              <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                                <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                              </svg>
                            )}
                          </span>
                          <span className="council-model-name">{shortName}</span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Toggle button */}
                  <button
                    type="button"
                    className={`council-models-toggle-btn${councilExpanded ? ' expanded' : ''}`}
                    onClick={() => setCouncilExpanded((v) => !v)}
                    aria-expanded={councilExpanded}
                    aria-label={councilExpanded ? 'Hide extra models' : `Show all ${available.length} models`}
                  >
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 12 12"
                      fill="none"
                      aria-hidden="true"
                      className="toggle-chevron"
                    >
                      <path d="M2 4L6 8L10 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    {councilExpanded
                      ? 'Hide extras ▴'
                      : `Show all ${available.length} models ▾`}
                    {!councilExpanded && extraCount > 0 && (
                      <span className="council-models-extra-badge">+{extraCount}</span>
                    )}
                  </button>
                </div>
              );
            })()}

            {/* ── Chairman accordion ── */}
            <div className="settings-subtitle settings-chairman-subtitle">
              <span>Chairman</span>
              <span className="settings-chairman-hint">Synthesizes the final verdict</span>
            </div>

            <div className="settings-chairman-accordion">
              {/* Selected chairman chip (always visible) */}
              <div className="settings-chairman-selected-row">
                {draftChairmanShort ? (
                  <div className="settings-chairman-chip">
                    <div className="settings-chairman-chip-bubble">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                      </svg>
                    </div>
                    <span className="settings-chairman-chip-name">{draftChairmanShort}</span>
                  </div>
                ) : (
                  <span className="settings-chairman-none">None selected</span>
                )}
                <button
                  className={`settings-chairman-toggle-btn${chairmanExpanded ? ' expanded' : ''}`}
                  onClick={() => setChairmanExpanded((v) => !v)}
                  aria-expanded={chairmanExpanded}
                  aria-label={chairmanExpanded ? 'Collapse chairman picker' : 'Change chairman'}
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true" className="toggle-chevron">
                    <path d="M2 4L6 8L10 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  {chairmanExpanded ? 'Collapse' : 'Change'}
                </button>
              </div>

              {/* Expandable picker */}
              {chairmanExpanded && (
                <div className="settings-chairman-picker" role="radiogroup" aria-label="Select chairman model">
                  {available.length === 0 && (
                    <p className="settings-empty-note">No models available.</p>
                  )}
                  {available.map((model) => {
                    const isChairman = draftChairman === model;
                    const shortName = model.split('/').pop();
                    return (
                      <div
                        key={model}
                        className={`settings-chairman-option${isChairman ? ' selected' : ''}`}
                        onClick={() => selectChairman(model)}
                        role="radio"
                        aria-checked={isChairman}
                        tabIndex={0}
                        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && selectChairman(model)}
                      >
                        <div className="settings-chairman-bubble">
                          {isChairman ? (
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                            </svg>
                          ) : (
                            <span className="settings-chairman-initial">{shortName[0]?.toUpperCase()}</span>
                          )}
                        </div>
                        <span className="settings-chairman-name">{shortName}</span>
                        {isChairman && (
                          <span className="settings-chairman-badge">✓</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="settings-subtitle">Appearance</div>
            <select
              className="settings-select"
              value={draftThemeMode}
              onChange={(e) => setDraftThemeMode(e.target.value)}
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </div>

          {/* Sticky footer with actions — even-width buttons */}
          <div className="settings-fullpanel-footer">
            <button className="settings-cancel-btn" onClick={closeSettings}>Cancel</button>
            <button className="settings-save-btn" onClick={save}>Save</button>
          </div>
        </div>
      )}

      {/* ── Normal sidebar content (hidden when settings open) ── */}
      {!showSettings && (
        <>
          <div className="sidebar-header">
            {/* Brand row: logo + settings gear */}
            <div className="sidebar-brand-row">
              {/* Logo image — falls back to text */}
              <div className="sidebar-logo-group">
                <img
                  src="/images/llm-council-icon.svg"
                  alt="LLM Council"
                  className="sidebar-logo-icon"
                  width="28"
                  height="28"
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
                <h1>LLM Council</h1>
              </div>
              {/* Static settings gear button — no rotation animation */}
              <button
                className="settings-icon-btn"
                aria-label="Open settings"
                title="Settings"
                onClick={openSettings}
              >
                <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path
                    d="M8.07 2.63A1 1 0 0 1 9.06 2h1.88a1 1 0 0 1 .99.63l.37 1A6.12 6.12 0 0 1 13.4 4.6l1.01-.35a1 1 0 0 1 1.16.39l.94 1.63a1 1 0 0 1-.18 1.21l-.76.7c.04.28.06.57.06.86s-.02.58-.06.86l.76.7a1 1 0 0 1 .18 1.21l-.94 1.63a1 1 0 0 1-1.16.39l-1.01-.35a6.12 6.12 0 0 1-1.1.97l-.37 1A1 1 0 0 1 10.94 18H9.06a1 1 0 0 1-.99-.63l-.37-1A6.12 6.12 0 0 1 6.6 15.4l-1.01.35a1 1 0 0 1-1.16-.39l-.94-1.63a1 1 0 0 1 .18-1.21l.76-.7A6.17 6.17 0 0 1 4.37 11a6.17 6.17 0 0 1 .06-.86l-.76-.7a1 1 0 0 1-.18-1.21l.94-1.63a1 1 0 0 1 1.16-.39l1.01.35a6.12 6.12 0 0 1 1.1-.97l.37-1Z"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                  <circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
                </svg>
              </button>
            </div>

            {/* Chairman bubble — visible when chairman is set */}
            {chairmanShort && (
              <div className="sidebar-chairman-row" onClick={openSettings} title="Edit chairman in Settings">
                <span className="sidebar-chairman-label">Chairman</span>
                <div className="sidebar-chairman-bubble">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                  </svg>
                  <span>{chairmanShort}</span>
                  <svg width="10" height="10" viewBox="0 0 20 20" fill="none" className="chairman-edit-icon" aria-hidden="true">
                    <path d="M14.5 2.5a2.121 2.121 0 0 1 3 3L6.5 16.5l-4 1 1-4L14.5 2.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round"/>
                  </svg>
                </div>
              </div>
            )}

            {/* New conversation button */}
            <button className="new-conversation-btn" onClick={onNewConversation}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
              </svg>
              New Conversation
            </button>
          </div>

          <div className="conversation-list">
            {conversations.length === 0 ? (
              <div className="no-conversations">No conversations yet</div>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`conversation-item ${
                    conv.id === currentConversationId ? 'active' : ''
                  } ${conv.pinned ? 'pinned' : ''}`}
                  onClick={() => onSelectConversation(conv.id)}
                >
                  <div className="conversation-row">
                    <div className="conversation-title">
                      {conv.pinned ? '📌 ' : ''}
                      {conv.title || 'New Conversation'}
                    </div>
                    <div className="conversation-actions">
                      <button
                        className="icon-btn"
                        title={conv.pinned ? 'Unpin conversation' : 'Pin conversation'}
                        onClick={(e) => {
                          e.stopPropagation();
                          onTogglePin(conv.id, !conv.pinned);
                        }}
                      >
                        {conv.pinned ? '📍' : '📌'}
                      </button>
                      <button
                        className="icon-btn danger"
                        title="Delete conversation"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteConversation(conv.id);
                        }}
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                  <div className="conversation-meta">{conv.message_count} messages</div>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
