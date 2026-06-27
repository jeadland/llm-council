import { useState, useEffect, useRef, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ChatInterface from "./components/ChatInterface";
import LoginScreen from "./components/LoginScreen";
import AppTopBar from "./components/AppTopBar";
import ModelPicker from "./components/ModelPicker";
import { api } from "./api";
import "./App.css";

const STORAGE_KEY = "llm-council-ui-v1";
const SIDEBAR_WIDTH_KEY = "llm-council-sidebar-width";
const SIDEBAR_MIN = 240;
const SIDEBAR_MAX = 480;

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [sidebarSettingsRequest, setSidebarSettingsRequest] = useState(null);
  const [activeRunId, setActiveRunId] = useState(null);
  const [settings, setSettings] = useState(null);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [modelCatalog, setModelCatalog] = useState([]);
  const [modelPresets, setModelPresets] = useState([]);
  const [openRouterStatus, setOpenRouterStatus] = useState(null);
  const [billingStatus, setBillingStatus] = useState(null);
  const [councilProfiles, setCouncilProfiles] = useState([]);
  const [adminFinance, setAdminFinance] = useState(null);
  const [sendError, setSendError] = useState("");
  const [authState, setAuthState] = useState({
    loading: true,
    authenticated: false,
    auth_required: true,
    email: null,
  });

  // Sidebar resize state — default 300px, restored from localStorage if valid
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    try {
      const saved = localStorage.getItem(SIDEBAR_WIDTH_KEY);
      if (saved) {
        const w = parseInt(saved, 10);
        if (!isNaN(w) && w >= SIDEBAR_MIN && w <= SIDEBAR_MAX) return w;
      }
    } catch {
      /* ignore */
    }
    return 300; // default width
  });
  const dragStartX = useRef(null);
  const dragStartWidth = useRef(null);
  const handleResizeStart = useCallback(
    (e) => {
      dragStartX.current = e.clientX;
      // Read current sidebar width from DOM at drag start
      const sidebarEl = document.querySelector(".sidebar");
      dragStartWidth.current = sidebarEl
        ? sidebarEl.getBoundingClientRect().width
        : sidebarWidth || 300;

      const onMove = (ev) => {
        const delta = ev.clientX - dragStartX.current;
        const newWidth = Math.min(
          SIDEBAR_MAX,
          Math.max(SIDEBAR_MIN, dragStartWidth.current + delta),
        );
        setSidebarWidth(newWidth);
      };

      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        // Persist to localStorage
        setSidebarWidth((w) => {
          if (w !== null) {
            try {
              localStorage.setItem(SIDEBAR_WIDTH_KEY, String(w));
            } catch {
              /* ignore */
            }
          }
          return w;
        });
        // Remove resize cursor from body
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
      // Prevent text selection and set global resize cursor during drag
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [sidebarWidth],
  );

  const applyTheme = useCallback((mode) => {
    const isDark =
      mode === "dark" ||
      (mode === "system" &&
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute(
      "data-theme",
      isDark ? "dark" : "light",
    );
  }, []);

  useEffect(() => {
    let frame = 0;
    const syncViewportHeight = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const height = window.visualViewport?.height || window.innerHeight;
        if (height) {
          document.documentElement.style.setProperty(
            "--app-viewport-height",
            `${height}px`,
          );
        }
      });
    };

    syncViewportHeight();
    window.visualViewport?.addEventListener("resize", syncViewportHeight);
    window.visualViewport?.addEventListener("scroll", syncViewportHeight);
    window.addEventListener("resize", syncViewportHeight);
    window.addEventListener("orientationchange", syncViewportHeight);

    return () => {
      cancelAnimationFrame(frame);
      window.visualViewport?.removeEventListener("resize", syncViewportHeight);
      window.visualViewport?.removeEventListener("scroll", syncViewportHeight);
      window.removeEventListener("resize", syncViewportHeight);
      window.removeEventListener("orientationchange", syncViewportHeight);
    };
  }, []);

  async function loadConversations() {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
      if (!currentConversationId && convs.length > 0) {
        setCurrentConversationId(convs[0].id);
      }
    } catch (error) {
      console.error("Failed to load conversations:", error);
    }
  }

  async function loadSettings() {
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (error) {
      console.error("Failed to load settings:", error);
    }
  }

  async function loadModelCatalog() {
    try {
      const data = await api.getModelCatalog();
      setModelCatalog(data.models || []);
      setModelPresets(data.presets || []);
    } catch (error) {
      console.error("Failed to load model catalog:", error);
    }
  }

  async function loadOpenRouterStatus() {
    try {
      const status = await api.getOpenRouterIntegration();
      setOpenRouterStatus(status);
      return status;
    } catch (error) {
      console.error("Failed to load OpenRouter integration:", error);
      return null;
    }
  }

  async function loadBillingStatus() {
    try {
      const status = await api.getBillingStatus();
      setBillingStatus(status);
      return status;
    } catch (error) {
      console.error("Failed to load billing status:", error);
      return null;
    }
  }

  async function loadCouncilProfiles() {
    try {
      const data = await api.getCouncilProfiles();
      setCouncilProfiles(data.profiles || []);
      return data.profiles || [];
    } catch (error) {
      console.error("Failed to load council profiles:", error);
      return [];
    }
  }

  async function loadAdminFinance(role = authState.role) {
    if (role !== "owner") return null;
    try {
      const data = await api.getAdminFinanceOverview();
      setAdminFinance(data);
      return data;
    } catch (error) {
      console.error("Failed to load admin finance overview:", error);
      return null;
    }
  }

  const handleSaveSettings = async (patch) => {
    try {
      const updated = await api.updateSettings(patch);
      setSettings(updated);
      return updated;
    } catch (error) {
      console.error("Failed to save settings:", error);
      throw error;
    }
  };

  const handleSaveCustomGroup = async (group) => {
    const groups = settings?.custom_model_groups || [];
    const existingIndex = groups.findIndex((item) => item.id === group.id);
    const nextGroups =
      existingIndex >= 0
        ? groups.map((item) => (item.id === group.id ? group : item))
        : [...groups, group];
    const updated = await handleSaveSettings({
      custom_model_groups: nextGroups,
    });
    return updated;
  };

  const openIntegrationsPanel = () => {
    setShowModelPicker(false);
    setSidebarSettingsRequest({
      section: "integrations",
      requestedAt: Date.now(),
    });
    setIsSidebarOpen(true);
  };

  const handleGoogleLogin = () => {
    api.loginWithGoogle();
  };

  const handleLogout = async () => {
    await api.logout();
    setAuthState({
      loading: false,
      authenticated: false,
      auth_required: true,
      email: null,
    });
    setConversations([]);
    setCurrentConversationId(null);
    setCurrentConversation(null);
    setActiveRunId(null);
    setIsLoading(false);
    setSendError("");
    setBillingStatus(null);
    setCouncilProfiles([]);
    setAdminFinance(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  async function loadConversation(id) {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error("Failed to load conversation:", error);
    }
  }

  function syncConversationWithRun(run) {
    setCurrentConversation((prev) => {
      if (!prev) return prev;
      const messages = [...prev.messages];
      const idx = messages.findIndex(
        (m) => m.role === "assistant" && m.run_id === run.run_id,
      );
      const costSummary =
        run.cost_summary || run.stage2?.metadata?.cost_summary || null;
      const billingReceipt =
        run.billing_receipt || run.stage2?.metadata?.billing_receipt || null;
      const stage1Execution = run.stage1?.metadata?.stage1_execution || null;
      const baseMetadata = { ...(run.stage2?.metadata || {}) };
      if (stage1Execution) baseMetadata.stage1_execution = stage1Execution;
      if (costSummary) baseMetadata.cost_summary = costSummary;
      if (billingReceipt) baseMetadata.billing_receipt = billingReceipt;
      const metadata = Object.keys(baseMetadata).length ? baseMetadata : null;
      const loading = {
        stage1: run.stage1?.status === "running",
        stage2: run.stage2?.status === "running",
        stage3: run.stage3?.status === "running",
      };

      const assistantMsg = {
        role: "assistant",
        run_id: run.run_id,
        stage1: run.stage1?.data || null,
        stage2: run.stage2?.data || null,
        stage3: run.stage3?.data || null,
        metadata,
        cost_summary: costSummary,
        billing_receipt: billingReceipt,
        loading,
        error:
          run.status === "failed"
            ? run.error || "An unknown error occurred"
            : null,
      };

      if (idx === -1) messages.push(assistantMsg);
      else messages[idx] = { ...messages[idx], ...assistantMsg };

      return { ...prev, messages };
    });
  }

  async function monitorRun(conversationId, runId) {
    setIsLoading(true);
    setActiveRunId(runId);

    await api.waitForRun(conversationId, runId, (run) => {
      syncConversationWithRun(run);
      if (
        run.status === "complete" ||
        run.status === "failed" ||
        run.status === "canceled"
      ) {
        setIsLoading(false);
        setActiveRunId(null);
      }
    });

    await loadConversation(conversationId);
    await loadConversations();
    await loadBillingStatus();
    await loadAdminFinance();
  }

  useEffect(() => {
    applyTheme(settings?.theme_mode || "system");
  }, [settings?.theme_mode, applyTheme]);

  useEffect(() => {
    const boot = async () => {
      try {
        const me = await api.getAuthMe();
        setAuthState({ loading: false, ...me });
        if (me.authenticated) {
          loadConversations();
          loadSettings();
          loadModelCatalog();
          loadOpenRouterStatus();
          loadBillingStatus();
          loadCouncilProfiles();
          loadAdminFinance(me.role);
          try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
            if (saved.currentConversationId)
              setCurrentConversationId(saved.currentConversationId);
            if (saved.activeRunId) setActiveRunId(saved.activeRunId);
          } catch {
            // ignore
          }
        }
      } catch (error) {
        console.error("Failed to check auth status:", error);
        setAuthState({
          loading: false,
          authenticated: false,
          auth_required: true,
          email: null,
        });
      }
    };

    boot();
  }, []);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ currentConversationId, activeRunId }),
    );
  }, [currentConversationId, activeRunId]);

  useEffect(() => {
    if (!currentConversationId) return;

    let canceled = false;
    const refreshConversation = async () => {
      try {
        const conv = await api.getConversation(currentConversationId);
        if (!canceled) setCurrentConversation(conv);

        const { run } = await api.getActiveRun(currentConversationId);
        if (!canceled && run) {
          await monitorRun(currentConversationId, run.run_id);
        }
      } catch (error) {
        if (!canceled) console.error("Failed to refresh conversation:", error);
      }
    };

    refreshConversation();
    return () => {
      canceled = true;
    };
  }, [currentConversationId]);

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        {
          id: newConv.id,
          created_at: newConv.created_at,
          message_count: 0,
          title: newConv.title,
        },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
      setIsSidebarOpen(false);
    } catch (error) {
      console.error("Failed to create conversation:", error);
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
      console.error("Failed to pin conversation:", error);
    }
  };

  const handleDeleteConversation = async (id) => {
    if (!window.confirm("Delete this conversation? This cannot be undone."))
      return;

    try {
      await api.deleteConversation(id);
      if (currentConversationId === id) {
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
      await loadConversations();
    } catch (error) {
      console.error("Failed to delete conversation:", error);
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
      console.error("Failed to stop run:", error);
    }
  };

  const handleBillingModeChange = async (mode) => {
    const status = await api.updateBillingMode(mode);
    setBillingStatus(status);
    return status;
  };

  const handleCheckout = async (packageId) => {
    const session = await api.createBillingCheckout(packageId);
    if (session?.url) {
      window.location.assign(session.url);
    }
    return session;
  };

  const handleManagedPauseChange = async (paused) => {
    const overview = await api.setManagedModePaused(paused);
    setAdminFinance(overview);
    return overview;
  };

  const handleSendMessage = async (content, runOptions = {}) => {
    if (!currentConversationId || isLoading) return;
    setSendError("");

    // Optimistic user message only; assistant progress comes from run snapshots
    setCurrentConversation((prev) => ({
      ...prev,
      messages: [...(prev?.messages || []), { role: "user", content }],
    }));

    try {
      const created = await api.createRun(currentConversationId, content, runOptions);
      await monitorRun(currentConversationId, created.run_id);
    } catch (error) {
      console.error("Failed to send message:", error);
      setSendError(error.message || "Failed to send message");
      setIsLoading(false);
    }
  };

  if (authState.loading) {
    return (
      <div className="app-loading">
        <div className="spinner"></div>
        <span>Loading LLM Council...</span>
      </div>
    );
  }

  if (authState.auth_required && !authState.authenticated) {
    return <LoginScreen onGoogleLogin={handleGoogleLogin} />;
  }

  const modelMap = new Map(modelCatalog.map((model) => [model.id, model]));

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
        onThemePreview={applyTheme}
        auth={authState}
        onLogout={handleLogout}
        onOpenRouterStatusChanged={setOpenRouterStatus}
        billingStatus={billingStatus}
        councilProfiles={councilProfiles}
        adminFinance={adminFinance}
        onBillingModeChange={handleBillingModeChange}
        onStartCheckout={handleCheckout}
        onRefreshBilling={async () => {
          await loadBillingStatus();
          await loadAdminFinance();
        }}
        onManagedPauseChange={handleManagedPauseChange}
        isOpen={isSidebarOpen}
        settingsRequest={sidebarSettingsRequest}
        onSettingsRequestHandled={() => setSidebarSettingsRequest(null)}
        sidebarWidth={sidebarWidth}
        onResizeStart={handleResizeStart}
      />

      {isSidebarOpen && (
        <div
          className="mobile-backdrop"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      <div className="chat-shell">
        <AppTopBar
          settings={settings}
          modelMap={modelMap}
          presets={modelPresets}
          onOpenModels={() => setShowModelPicker(true)}
          onOpenConversations={() => setIsSidebarOpen((v) => !v)}
        />

        <ChatInterface
          conversation={currentConversation}
          onSendMessage={handleSendMessage}
          onStopRun={handleStopRun}
          onCreateConversation={handleNewConversation}
          isLoading={isLoading}
          activeRunId={activeRunId}
          sendError={sendError}
          settings={settings}
          onOpenModels={() => setShowModelPicker(true)}
          onOpenIntegrations={openIntegrationsPanel}
          openRouterStatus={openRouterStatus}
          billingStatus={billingStatus}
          councilProfiles={councilProfiles}
          modelMap={modelMap}
          presets={modelPresets}
        />
      </div>

      <ModelPicker
        open={showModelPicker}
        selectedCouncil={settings?.council_models || []}
        selectedChairman={settings?.chairman_model || ""}
        activeGroupId={settings?.active_model_group_id || ""}
        customGroups={settings?.custom_model_groups || []}
        onApply={async (patch) => {
          await handleSaveSettings(patch);
          await loadModelCatalog();
        }}
        onSaveCustomGroup={handleSaveCustomGroup}
        onCurationApproved={(updatedSettings) => {
          setSettings(updatedSettings);
          loadModelCatalog();
        }}
        onOpenIntegrations={openIntegrationsPanel}
        onClose={() => setShowModelPicker(false)}
      />
    </div>
  );
}

export default App;
