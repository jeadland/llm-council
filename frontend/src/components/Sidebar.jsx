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

  const available = settings?.available_models || [];

  const toggleModel = (model) => {
    setDraftCouncil((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model]
    );
  };

  const save = async () => {
    const safeCouncil = draftCouncil.length ? draftCouncil : settings?.council_models || [];
    const safeChairman = draftChairman || settings?.chairman_model;
    await onSaveSettings({ council_models: safeCouncil, chairman_model: safeChairman });
    setShowSettings(false);
  };

  return (
    <div className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>
        <button
          className="settings-btn"
          onClick={() => {
            setDraftCouncil(settings?.council_models || []);
            setDraftChairman(settings?.chairman_model || '');
            setShowSettings((v) => !v);
          }}
        >
          ⚙ Settings
        </button>
      </div>

      {showSettings && (
        <div className="settings-panel">
          <div className="settings-title">Model Picker</div>
          <div className="settings-subtitle">Council Models</div>
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
