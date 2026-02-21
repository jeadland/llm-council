import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

const STORAGE_KEY = 'llm-council-ui-v1';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [activeRunId, setActiveRunId] = useState(null);
  const [settings, setSettings] = useState(null);

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

          {/* Quick new-chat button — saves a sidebar open/close cycle */}
          <button
            className="mobile-new-btn"
            onClick={handleNewConversation}
            aria-label="New conversation"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M10 3.5V16.5M3.5 10H16.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
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
