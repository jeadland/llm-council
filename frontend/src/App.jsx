import { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

const STORAGE_KEY = 'llm-council-ui-v1';
const SIDEBAR_WIDTH_KEY = 'llm-council-sidebar-width';
const SIDEBAR_MIN = 240;
const SIDEBAR_MAX = 480;

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [openSettingsOnSidebarOpen, setOpenSettingsOnSidebarOpen] = useState(false);
  const [activeRunId, setActiveRunId] = useState(null);
  const [settings, setSettings] = useState(null);

  // Sidebar resize state
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    try {
      const saved = localStorage.getItem(SIDEBAR_WIDTH_KEY);
      if (saved) {
        const w = parseInt(saved, 10);
        if (!isNaN(w) && w >= SIDEBAR_MIN && w <= SIDEBAR_MAX) return w;
      }
    } catch { /* ignore */ }
    return null; // null = use CSS default
  });
  const dragStartX = useRef(null);
  const dragStartWidth = useRef(null);
  const sidebarRef = useRef(null);

  const handleResizeStart = useCallback((e) => {
    dragStartX.current = e.clientX;
    // Read current sidebar width from DOM at drag start
    const sidebarEl = document.querySelector('.sidebar');
    dragStartWidth.current = sidebarEl ? sidebarEl.getBoundingClientRect().width : (sidebarWidth || 300);

    const onMove = (ev) => {
      const delta = ev.clientX - dragStartX.current;
      const newWidth = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, dragStartWidth.current + delta));
      setSidebarWidth(newWidth);
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      // Persist to localStorage
      setSidebarWidth((w) => {
        if (w !== null) {
          try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(w)); } catch { /* ignore */ }
        }
        return w;
      });
      // Remove resize cursor from body
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    // Prevent text selection and set global resize cursor during drag
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [sidebarWidth]);

  useEffect(() => {
    const mode = settings?.theme_mode || 'system';
    const isDark =
      mode === 'dark' ||
      (mode === 'system' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  }, [settings?.theme_mode]);

  useEffect(() => {
    loadConversations();
    loadSettings();
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      if (saved.currentConversationId) setCurrentConversationId(saved.currentConversationId);
      if (saved.activeRunId) setActiveRunId(saved.activeRunId);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ currentConversationId, activeRunId })
    );
  }, [currentConversationId, activeRunId]);

  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
      checkForActiveRun(currentConversationId);
    }
  }, [currentConversationId]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
      if (!currentConversationId && convs.length > 0) {
        setCurrentConversationId(convs[0].id);
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadSettings = async () => {
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };

  const handleSaveSettings = async (patch) => {
    try {
      const updated = await api.updateSettings(patch);
      setSettings(updated);
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const syncConversationWithRun = (run) => {
    setCurrentConversation((prev) => {
      if (!prev) return prev;
      const messages = [...prev.messages];
      const idx = messages.findIndex((m) => m.role === 'assistant' && m.run_id === run.run_id);
      const loading = {
        stage1: run.stage1?.status === 'running',
        stage2: run.stage2?.status === 'running',
        stage3: run.stage3?.status === 'running',
      };

      const assistantMsg = {
        role: 'assistant',
        run_id: run.run_id,
        stage1: run.stage1?.data || null,
        stage2: run.stage2?.data || null,
        stage3: run.stage3?.data || null,
        metadata: run.stage2?.metadata || null,
        loading,
        error: run.status === 'failed' ? (run.error || 'An unknown error occurred') : null,
      };

      if (idx === -1) messages.push(assistantMsg);
      else messages[idx] = { ...messages[idx], ...assistantMsg };

      return { ...prev, messages };
    });
  };

  const monitorRun = async (conversationId, runId) => {
    setIsLoading(true);
    setActiveRunId(runId);

    await api.waitForRun(conversationId, runId, (run) => {
      syncConversationWithRun(run);
      if (run.status === 'complete' || run.status === 'failed' || run.status === 'canceled') {
        setIsLoading(false);
        setActiveRunId(null);
      }
    });

    await loadConversation(conversationId);
    await loadConversations();
  };

  const checkForActiveRun = async (conversationId) => {
    try {
      const { run } = await api.getActiveRun(conversationId);
      if (run) {
        await monitorRun(conversationId, run.run_id);
      }
    } catch (e) {
      console.error('Failed checking active run:', e);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0, title: newConv.title },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
      setIsSidebarOpen(false);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
    setIsSidebarOpen(false);
  };

  const handleTogglePin = async (id, pinned) => {
    try {
      await api.pinConversation(id, pinned);
      await loadConversations();
      if (currentConversationId === id) {
        await loadConversation(id);
      }
    } catch (error) {
      console.error('Failed to pin conversation:', error);
    }
  };

  const handleDeleteConversation = async (id) => {
    if (!window.confirm('Delete this conversation? This cannot be undone.')) return;

    try {
      await api.deleteConversation(id);
      if (currentConversationId === id) {
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
      await loadConversations();
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleStopRun = async () => {
    if (!currentConversationId || !activeRunId) return;
    try {
      await api.stopRun(currentConversationId, activeRunId);
      setIsLoading(false);
      setActiveRunId(null);
      await loadConversation(currentConversationId);
      await loadConversations();
    } catch (error) {
      console.error('Failed to stop run:', error);
    }
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId || isLoading) return;

    // Optimistic user message only; assistant progress comes from run snapshots
    setCurrentConversation((prev) => ({
      ...prev,
      messages: [...(prev?.messages || []), { role: 'user', content }],
    }));

    try {
      const created = await api.createRun(currentConversationId, content);
      await monitorRun(currentConversationId, created.run_id);
    } catch (error) {
      console.error('Failed to send message:', error);
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onTogglePin={handleTogglePin}
        onDeleteConversation={handleDeleteConversation}
        settings={settings}
        onSaveSettings={handleSaveSettings}
        isOpen={isSidebarOpen}
        openSettingsOnOpen={openSettingsOnSidebarOpen}
        onSettingsOpened={() => setOpenSettingsOnSidebarOpen(false)}
        sidebarWidth={sidebarWidth}
        onResizeStart={handleResizeStart}
      />

      {isSidebarOpen && <div className="mobile-backdrop" onClick={() => setIsSidebarOpen(false)} />}

      <div className="chat-shell">
        <div className="mobile-topbar">
          <button
            className="mobile-menu-btn"
            onClick={() => setIsSidebarOpen((v) => !v)}
            aria-label="Open conversations"
          >
            {/* Hamburger SVG — crisp, accessible */}
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <rect x="2" y="4.5" width="16" height="2" rx="1" fill="currentColor"/>
              <rect x="2" y="9"   width="16" height="2" rx="1" fill="currentColor"/>
              <rect x="2" y="13.5" width="16" height="2" rx="1" fill="currentColor"/>
            </svg>
          </button>

          <div className="mobile-title-group">
            <img
              src="/images/llm-council-icon.svg"
              alt=""
              className="mobile-logo-icon"
              width="22"
              height="22"
              aria-hidden="true"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
            <span className="mobile-title">LLM Council</span>
          </div>

          {/* Settings gear — exact same SVG/styling as sidebar gear */}
          <button
            className="mobile-settings-btn settings-icon-btn"
            onClick={() => {
              setOpenSettingsOnSidebarOpen(true);
              setIsSidebarOpen(true);
            }}
            aria-label="Open settings"
            title="Settings"
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

        <ChatInterface
          conversation={currentConversation}
          onSendMessage={handleSendMessage}
          onStopRun={handleStopRun}
          onCreateConversation={handleNewConversation}
          isLoading={isLoading}
          activeRunId={activeRunId}
          settings={settings}
        />
      </div>
    </div>
  );
}

export default App;
