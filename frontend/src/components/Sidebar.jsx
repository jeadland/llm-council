import { useState } from 'react';
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
}) {
  const [showSettings, setShowSettings] = useState(false);
  const [draftCouncil, setDraftCouncil] = useState(settings?.council_models || []);
  const [draftChairman, setDraftChairman] = useState(settings?.chairman_model || '');
  const [draftThemeMode, setDraftThemeMode] = useState(settings?.theme_mode || 'system');

  const available = settings?.available_models || [];

  const toggleModel = (model) => {
    setDraftCouncil((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model]
    );
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
  };

  return (
    <div className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        {/* Brand row: title + settings gear */}
        <div className="sidebar-brand-row">
          <h1>LLM Council</h1>
          <button
            className={`settings-icon-btn${showSettings ? ' active' : ''}`}
            aria-label={showSettings ? 'Close settings' : 'Open settings'}
            title="Settings"
            onClick={() => {
              setDraftCouncil(settings?.council_models || []);
              setDraftChairman(settings?.chairman_model || '');
              setDraftThemeMode(settings?.theme_mode || 'system');
              setShowSettings((v) => !v);
            }}
          >
            {/* Gear SVG */}
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

        {/* New conversation button */}
        <button className="new-conversation-btn" onClick={onNewConversation}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
          </svg>
          New Conversation
        </button>
      </div>

      {showSettings && (
        <div className="settings-panel">
          <div className="settings-title">Model Picker</div>
          <div className="settings-subtitle">Your Available Models</div>
          {available.map((model) => (
            <label key={model} className="settings-row">
              <input
                type="checkbox"
                checked={draftCouncil.includes(model)}
                onChange={() => toggleModel(model)}
              />
              <span>{model}</span>
            </label>
          ))}

          <div className="settings-subtitle">Chairman</div>
          <select
            className="settings-select"
            value={draftChairman}
            onChange={(e) => setDraftChairman(e.target.value)}
          >
            {available.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>

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

          <button className="settings-save-btn" onClick={save}>Save Settings</button>
        </div>
      )}

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
    </div>
  );
}
