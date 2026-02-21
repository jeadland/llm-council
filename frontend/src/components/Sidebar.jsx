import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onTogglePin,
  onDeleteConversation,
  isOpen,
}) {
  return (
    <div className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
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
              <div className="conversation-meta">
                {conv.message_count} messages
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
