import { useState, useEffect, useCallback, useRef } from "react";
import { LogOut, Settings as SettingsIcon, UserCircle } from "lucide-react";
import { api } from "../api";
import "./Sidebar.css";

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onTogglePin,
  onDeleteConversation,
  settings,
  onSaveSettings,
  onThemePreview,
  auth,
  onLogout,
  onOpenRouterStatusChanged,
  isOpen,
  settingsRequest,
  onSettingsRequestHandled,
  sidebarWidth,
  onResizeStart,
}) {
  const [showSettings, setShowSettings] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const integrationCardRef = useRef(null);
  const focusIntegrationsRef = useRef(false);

  const handleResizeMouseDown = useCallback(
    (e) => {
      e.preventDefault();
      setIsDragging(true);
      onResizeStart?.(e);
    },
    [onResizeStart],
  );

  useEffect(() => {
    if (!isDragging) return;
    const onUp = () => setIsDragging(false);
    window.addEventListener("mouseup", onUp);
    return () => window.removeEventListener("mouseup", onUp);
  }, [isDragging]);
  const [draftThemeMode, setDraftThemeMode] = useState(
    settings?.theme_mode || "system",
  );
  const [openRouterStatus, setOpenRouterStatus] = useState(null);
  const [openRouterKey, setOpenRouterKey] = useState("");
  const [openRouterStatusMessage, setOpenRouterStatusMessage] = useState("");
  const [openRouterBusy, setOpenRouterBusy] = useState(false);

  const loadOpenRouterStatus = useCallback(async () => {
    try {
      const status = await api.getOpenRouterIntegration();
      setOpenRouterStatus(status);
      onOpenRouterStatusChanged?.(status);
    } catch (e) {
      setOpenRouterStatusMessage(
        e.message || "Could not load OpenRouter status.",
      );
    }
  }, [onOpenRouterStatusChanged]);

  const scrollToIntegrations = useCallback(() => {
    requestAnimationFrame(() => {
      integrationCardRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }, []);

  const openSettings = ({ focusIntegrations = false } = {}) => {
    focusIntegrationsRef.current = focusIntegrations;
    setDraftThemeMode(settings?.theme_mode || "system");
    setOpenRouterKey("");
    setOpenRouterStatusMessage("");
    setShowSettings(true);
  };

  const closeSettings = () => {
    // Revert live theme preview to the saved/persisted setting
    if (onThemePreview) onThemePreview(settings?.theme_mode || "system");
    setShowSettings(false);
  };

  useEffect(() => {
    if (!settingsRequest) return;
    const focusIntegrations = settingsRequest.section === "integrations";
    const wasOpen = showSettings;
    openSettings({ focusIntegrations });
    if (focusIntegrations && wasOpen) {
      focusIntegrationsRef.current = false;
      scrollToIntegrations();
    }
    onSettingsRequestHandled?.();
  }, [settingsRequest]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!showSettings) return;
    loadOpenRouterStatus();
    if (focusIntegrationsRef.current) {
      focusIntegrationsRef.current = false;
      scrollToIntegrations();
    }
  }, [showSettings, loadOpenRouterStatus, scrollToIntegrations]);

  const save = async () => {
    await onSaveSettings({
      theme_mode: draftThemeMode,
    });
    setShowSettings(false);
  };

  const submitOpenRouterKey = async () => {
    setOpenRouterStatusMessage("");
    setOpenRouterBusy(true);
    try {
      const status = await api.updateOpenRouterIntegration({
        api_key: openRouterKey,
      });
      setOpenRouterStatus(status);
      onOpenRouterStatusChanged?.(status);
      setOpenRouterKey("");
      setOpenRouterStatusMessage("OpenRouter key saved.");
    } catch (e) {
      setOpenRouterStatusMessage(
        e.message || "OpenRouter key could not be saved.",
      );
    } finally {
      setOpenRouterBusy(false);
    }
  };

  const clearOpenRouterKey = async () => {
    setOpenRouterStatusMessage("");
    setOpenRouterBusy(true);
    try {
      const status = await api.updateOpenRouterIntegration({ clear: true });
      setOpenRouterStatus(status);
      onOpenRouterStatusChanged?.(status);
      setOpenRouterKey("");
      setOpenRouterStatusMessage("OpenRouter account key cleared.");
    } catch (e) {
      setOpenRouterStatusMessage(
        e.message || "OpenRouter key could not be cleared.",
      );
    } finally {
      setOpenRouterBusy(false);
    }
  };

  const accountTitle = auth?.role === "owner" ? "Owner" : "Account";
  const ownerLabel =
    auth?.name ||
    auth?.email ||
    (auth?.auth_required ? "Account" : "Local session");
  const accountSubLabel = auth?.name && auth?.email ? auth.email : ownerLabel;
  const ownerInitial = (auth?.name || auth?.email || "L")
    .trim()
    .slice(0, 1)
    .toUpperCase();

  return (
    <div
      className={`sidebar ${isOpen ? "open" : ""} ${showSettings ? "settings-fullpanel" : ""}`}
      style={
        sidebarWidth ? { "--sidebar-width": `${sidebarWidth}px` } : undefined
      }
    >
      {/* Drag resize handle — desktop only, hidden on mobile via CSS */}
      <div
        className={`sidebar-resize-handle${isDragging ? " dragging" : ""}`}
        onMouseDown={handleResizeMouseDown}
        aria-hidden="true"
      >
        <span className="sidebar-resize-tooltip">Drag to resize</span>
      </div>

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
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M10 3L5 8L10 13"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            <span className="settings-fullpanel-title">Settings</span>
          </div>

          {/* Settings body — scrollable */}
          <div className="settings-fullpanel-body">
            <div className="settings-subtitle">Appearance</div>
            <div
              className="appearance-icon-row"
              role="group"
              aria-label="Theme mode"
            >
              {/* Light — Sun */}
              <button
                className={`appearance-icon-btn${draftThemeMode === "light" ? " selected" : ""}`}
                onClick={() => {
                  setDraftThemeMode("light");
                  onThemePreview?.("light");
                }}
                aria-pressed={draftThemeMode === "light"}
                title="Light"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill={draftThemeMode === "light" ? "currentColor" : "none"}
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="4" />
                  <line x1="12" y1="2" x2="12" y2="5" />
                  <line x1="12" y1="19" x2="12" y2="22" />
                  <line x1="4.22" y1="4.22" x2="6.34" y2="6.34" />
                  <line x1="17.66" y1="17.66" x2="19.78" y2="19.78" />
                  <line x1="2" y1="12" x2="5" y2="12" />
                  <line x1="19" y1="12" x2="22" y2="12" />
                  <line x1="4.22" y1="19.78" x2="6.34" y2="17.66" />
                  <line x1="17.66" y1="6.34" x2="19.78" y2="4.22" />
                </svg>
                <span>Light</span>
              </button>

              {/* Dark — Moon */}
              <button
                className={`appearance-icon-btn${draftThemeMode === "dark" ? " selected" : ""}`}
                onClick={() => {
                  setDraftThemeMode("dark");
                  onThemePreview?.("dark");
                }}
                aria-pressed={draftThemeMode === "dark"}
                title="Dark"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill={draftThemeMode === "dark" ? "currentColor" : "none"}
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
                <span>Dark</span>
              </button>

              {/* System — Monitor */}
              <button
                className={`appearance-icon-btn${draftThemeMode === "system" ? " selected" : ""}`}
                onClick={() => {
                  setDraftThemeMode("system");
                  onThemePreview?.("system");
                }}
                aria-pressed={draftThemeMode === "system"}
                title="System"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill={draftThemeMode === "system" ? "currentColor" : "none"}
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
                <span>System</span>
              </button>
            </div>

            <div className="settings-subtitle settings-account-subtitle">
              <span>API &amp; Integrations</span>
              <span className="settings-chairman-hint">
                {openRouterStatus?.configured
                  ? "Configured"
                  : "Required for hosted direct runs"}
              </span>
            </div>
            <div className="integration-settings-card" ref={integrationCardRef}>
              <div className="integration-card-header">
                <div>
                  <strong>OpenRouter</strong>
                  <span>
                    {openRouterStatus?.configured
                      ? openRouterStatus.source === "environment"
                        ? "Configured by server environment"
                        : `Your key is saved (${openRouterStatus.masked_key})`
                      : "No key saved"}
                  </span>
                </div>
                <span
                  className={`integration-status-pill${openRouterStatus?.configured ? " configured" : ""}`}
                >
                  {openRouterStatus?.configured ? "Ready" : "Needs key"}
                </span>
              </div>
              <p>
                Your OpenRouter key pays for your council runs. The full key is
                stored server-side only and is never returned to the browser.
              </p>
              <label className="account-field">
                <span>OpenRouter API key</span>
                <input
                  id="llm-council-settings-openrouter-api-key"
                  name="openrouter-api-key"
                  type="password"
                  autoComplete="off"
                  value={openRouterKey}
                  onChange={(e) => setOpenRouterKey(e.target.value)}
                  placeholder={
                    openRouterStatus?.configured
                      ? "Leave blank to keep the saved key"
                      : "sk-or-v1-..."
                  }
                />
              </label>
              {openRouterStatusMessage && (
                <div
                  className={`account-status${openRouterStatusMessage.includes("saved") || openRouterStatusMessage.includes("cleared") ? " success" : ""}`}
                >
                  {openRouterStatusMessage}
                </div>
              )}
              <div className="account-actions integration-actions">
                <button
                  type="button"
                  className="settings-save-btn account-password-btn"
                  onClick={submitOpenRouterKey}
                  disabled={openRouterBusy || !openRouterKey.trim()}
                >
                  {openRouterBusy ? "Saving..." : "Save key"}
                </button>
                <button
                  type="button"
                  className="settings-cancel-btn account-logout-btn"
                  onClick={clearOpenRouterKey}
                  disabled={
                    openRouterBusy || openRouterStatus?.source !== "account"
                  }
                >
                  Clear account key
                </button>
              </div>
            </div>

            {auth?.auth_required && (
              <>
                <div className="settings-subtitle settings-account-subtitle">
                  <span>Account</span>
                  <span className="settings-chairman-hint">{auth.email}</span>
                </div>
                <div className="account-settings">
                  <div className="account-status success">
                    Signed in with Google. Sign out from the menu below.
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Sticky footer with actions — even-width buttons */}
          <div className="settings-fullpanel-footer">
            <button className="settings-cancel-btn" onClick={closeSettings}>
              Cancel
            </button>
            <button className="settings-save-btn" onClick={save}>
              Save
            </button>
          </div>
        </div>
      )}

      {/* ── Normal sidebar content (hidden when settings open) ── */}
      {!showSettings && (
        <>
          <div className="sidebar-header">
            <div className="sidebar-brand-row">
              <div className="sidebar-logo-group">
                <img
                  src={`${import.meta.env.BASE_URL}images/llm-council-icon.svg`}
                  alt="LLM Council"
                  className="sidebar-logo-icon"
                  width="28"
                  height="28"
                  onError={(e) => {
                    e.target.style.display = "none";
                  }}
                />
                <h1>LLM Council</h1>
              </div>
            </div>

            <button
              className="new-conversation-btn"
              onClick={onNewConversation}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 16 16"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M8 2v12M2 8h12"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                />
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
                    conv.id === currentConversationId ? "active" : ""
                  } ${conv.pinned ? "pinned" : ""}`}
                  onClick={() => onSelectConversation(conv.id)}
                >
                  <div className="conversation-row">
                    <div className="conversation-title">
                      {conv.title || "New Conversation"}
                    </div>
                    <div className="conversation-actions">
                      <button
                        className={`icon-btn pin-btn${conv.pinned ? " pinned" : ""}`}
                        title={
                          conv.pinned
                            ? "Unpin conversation"
                            : "Pin conversation"
                        }
                        onClick={(e) => {
                          e.stopPropagation();
                          onTogglePin(conv.id, !conv.pinned);
                        }}
                      >
                        {conv.pinned ? (
                          /* Filled pushpin — conversation IS pinned */
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="currentColor"
                            stroke="none"
                            aria-hidden="true"
                          >
                            <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17z" />
                            <rect
                              x="11.25"
                              y="17"
                              width="1.5"
                              height="5"
                              rx="0.75"
                            />
                          </svg>
                        ) : (
                          /* Outline pushpin — conversation is NOT pinned */
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                          >
                            <path d="M12 17v5M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17z" />
                          </svg>
                        )}
                      </button>
                      <button
                        className="icon-btn danger"
                        title="Delete conversation"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteConversation(conv.id);
                        }}
                      >
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden="true"
                        >
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                          <line x1="10" y1="11" x2="10" y2="17" />
                          <line x1="14" y1="11" x2="14" y2="17" />
                        </svg>
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

          <div className="sidebar-footer">
            <div className="sidebar-owner">
              <div className="sidebar-owner-avatar" aria-hidden="true">
                {auth?.email ? ownerInitial : <UserCircle size={18} />}
              </div>
              <div className="sidebar-owner-copy">
                <span className="sidebar-owner-title">{accountTitle}</span>
                <span className="sidebar-owner-email">{accountSubLabel}</span>
              </div>
              <button
                type="button"
                className="sidebar-owner-settings"
                onClick={() => openSettings()}
                aria-label="Settings"
                title="Settings"
              >
                <SettingsIcon size={18} />
              </button>
            </div>

            {auth?.auth_required && (
              <button
                type="button"
                className="sidebar-footer-action is-danger"
                onClick={onLogout}
              >
                <LogOut size={16} />
                <span>Sign out</span>
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
