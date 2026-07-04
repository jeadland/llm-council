import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { LogOut, Pin, Settings as SettingsIcon, UserCircle } from "lucide-react";
import { api } from "../api";
import { shortModelName } from "../modelUtils";
import "./Sidebar.css";

const formatUsd = (value) => `$${Number(value || 0).toFixed(2)}`;
const packageConfigured = (pkg) => pkg?.configured !== false;

function buildCoverageGuidance(coverage) {
  if (!coverage || coverage.status === "not_configured") {
    return {
      tone: "muted",
      headline: "OpenRouter management not configured",
      action: "Set OPENROUTER_MANAGEMENT_KEY to enable live balance checks.",
    };
  }
  if (coverage.status === "unknown") {
    return {
      tone: "muted",
      headline: "No live snapshot yet",
      action: "Refresh to pull OpenRouter credits and compute the target floor.",
    };
  }

  const available = Number(coverage.available_credits_usd);
  const floor = Number(coverage.required_floor_usd);
  const gap = floor - available;
  const hasNumbers = Number.isFinite(available) && Number.isFinite(floor);

  if (!hasNumbers) {
    return {
      tone: "muted",
      headline: "Coverage data incomplete",
      action: "Refresh the OpenRouter balance snapshot.",
    };
  }

  if (gap > 0.5) {
    const topUp = Math.max(5, Math.ceil(gap / 5) * 5);
    const urgent = coverage.status === "emergency" || coverage.status === "critical";
    return {
      tone: urgent ? "danger" : "warn",
      headline: `Below target by ${formatUsd(gap)}`,
      action: urgent
        ? `Add about ${formatUsd(topUp)} to OpenRouter and consider pausing balance runs.`
        : `Add about ${formatUsd(topUp)} to OpenRouter to restore the safety floor.`,
    };
  }

  const surplus = Math.abs(gap);
  return {
    tone: coverage.status === "healthy" ? "good" : "warn",
    headline: surplus > 0.5 ? `Above target by ${formatUsd(surplus)}` : "On target",
    action:
      coverage.status === "healthy"
        ? "No action needed."
        : `Status is ${coverage.status}. Monitor after the next managed runs.`,
  };
}

const plainProfileName = (profile) =>
  (profile?.display_name || "Balanced Council").replace(" Council", "");

const questionFitCopy = (pkg, councilProfiles = []) => {
  const amount = Number(pkg?.amount_usd || 0);
  const profile =
    councilProfiles.find((item) => item.slug === "balanced") ||
    councilProfiles.find((item) => item.pricing_available);
  const low = Number(profile?.estimated_app_cost_low_usd || 0);
  const high = Number(profile?.estimated_app_cost_high_usd || 0);
  const cap = Number(profile?.max_user_visible_charge_usd || high || 0);
  const upperCost = cap > 0 ? Math.min(high || cap, cap) : high;

  if (pkg?.test || pkg?.id === "test_1") {
    return "Small checkout and webhook test top-up.";
  }

  if (amount > 0 && low > 0 && upperCost > 0) {
    const minQuestions = Math.max(1, Math.floor(amount / upperCost));
    const maxQuestions = Math.max(minQuestions, Math.floor(amount / low));
    const count =
      minQuestions === maxQuestions
        ? `${minQuestions}`
        : `${minQuestions}-${maxQuestions}`;
    return `About ${count} ${plainProfileName(profile).toLowerCase()} questions.`;
  }

  if (pkg?.id === "starter_5") return "Good for trying a few everyday questions.";
  if (pkg?.id === "power_20") return "Good for heavier planning or deeper sessions.";
  return "Good for a normal batch of planning and writing questions.";
};

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
  billingStatus,
  billingStatusError,
  billingNotice,
  councilProfiles,
  adminFinance,
  onBillingModeChange,
  onStartCheckout,
  onRefreshBilling,
  onManagedPauseChange,
  isOpen,
  isPinned = false,
  onToggleSidebarPin,
  onRefreshAdminCoverage,
  settingsRequest,
  onSettingsRequestHandled,
  sidebarWidth,
  onResizeStart,
  onOpenModels,
}) {
  const [showSettings, setShowSettings] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [coverageBusy, setCoverageBusy] = useState(false);
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
  const [billingMessage, setBillingMessage] = useState("");
  const [billingBusy, setBillingBusy] = useState(false);
  const [settingsView, setSettingsView] = useState("settings");
  const [addBalanceOpen, setAddBalanceOpen] = useState(false);
  const [selectedTopupId, setSelectedTopupId] = useState("");
  const [settingsDialog, setSettingsDialog] = useState(null);
  const councilModelCount = settings?.council_models?.length || 0;
  const chairmanLabel = shortModelName(settings?.chairman_model) || "None";

  const openCouncilSetup = () => {
    setShowSettings(false);
    setSettingsDialog(null);
    onOpenModels?.();
  };

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
    setBillingMessage("");
    setSettingsView("settings");
    setAddBalanceOpen(false);
    setSettingsDialog(focusIntegrations ? "model-access" : null);
    setShowSettings(true);
  };

  const closeSettings = () => {
    setSettingsDialog(null);
    setShowSettings(false);
  };

  useEffect(() => {
    if (!settingsRequest) return;
    const focusIntegrations = settingsRequest.section === "integrations";
    const wasOpen = showSettings;
    openSettings({ focusIntegrations });
    if (settingsRequest.action === "add-balance" && canAddBalance) {
      setSelectedTopupId(recommendedTopup?.id || "");
      setAddBalanceOpen(true);
    }
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

  const selectThemeMode = async (mode) => {
    setDraftThemeMode(mode);
    onThemePreview?.(mode);
    try {
      await onSaveSettings({ theme_mode: mode });
    } catch (error) {
      console.error("Theme could not be saved:", error);
    }
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

  const updateBillingMode = async (mode) => {
    setBillingMessage("");
    setBillingBusy(true);
    try {
      await onBillingModeChange?.(mode);
      setBillingMessage(
        mode === "managed"
          ? "LLM Council Balance will be used for future runs."
          : "Your OpenRouter key will be used for future runs.",
      );
    } catch (e) {
      setBillingMessage(e.message || "Billing mode could not be updated.");
    } finally {
      setBillingBusy(false);
    }
  };

  const startCheckout = async (packageId) => {
    setBillingMessage("");
    setBillingBusy(true);
    try {
      await onStartCheckout?.(packageId);
    } catch (e) {
      setBillingMessage(e.message || "Checkout could not be started.");
      setBillingBusy(false);
    }
  };

  const topupPackages = billingStatus?.topup_packages || [];
  const configuredTopupPackages = topupPackages.filter(packageConfigured);
  const recommendedTopup =
    configuredTopupPackages.find((pkg) => pkg.recommended) ||
    configuredTopupPackages[0] ||
    null;
  const selectedTopup =
    configuredTopupPackages.find((pkg) => pkg.id === selectedTopupId) || recommendedTopup;
  const availableBalance = Number(billingStatus?.available_balance_usd || 0);
  const canAddBalance =
    !billingStatusError &&
    Boolean(billingStatus?.managed_mode_enabled) &&
    Boolean(billingStatus?.stripe_configured) &&
    configuredTopupPackages.length > 0;
  const canUseManagedBalance =
    !billingStatusError &&
    Boolean(billingStatus?.managed_mode_enabled) &&
    availableBalance > 0;
  const managedBalanceActive = billingStatus?.billing_mode === "managed";
  const managedBalanceModeLabel = managedBalanceActive
    ? "Balance will be used for runs"
    : "Use balance for runs";
  const balanceStatusLabel = billingStatusError
    ? "Check status"
    : canAddBalance
      ? "Ready"
      : billingStatus?.managed_mode_enabled
        ? "Setup needed"
        : "Private beta";
  const balanceSummary = billingStatusError
    ? "Billing status could not be loaded."
    : canAddBalance
      ? "Add balance through Stripe Checkout."
      : billingStatus?.managed_mode_enabled
        ? "Stripe setup is incomplete."
        : "Use OpenRouter key access until the private beta is enabled.";

  const openAddBalance = () => {
    setBillingMessage("");
    setSelectedTopupId(recommendedTopup?.id || "");
    setAddBalanceOpen(true);
  };

  const confirmAddBalance = () => {
    if (!selectedTopup?.id) return;
    startCheckout(selectedTopup.id);
  };

  const toggleManagedPause = async (paused) => {
    setBillingMessage("");
    setBillingBusy(true);
    try {
      await onManagedPauseChange?.(paused);
      setBillingMessage(paused ? "Managed runs paused." : "Managed runs resumed.");
      await onRefreshBilling?.();
    } catch (e) {
      setBillingMessage(e.message || "Managed mode could not be updated.");
    } finally {
      setBillingBusy(false);
    }
  };

  const refreshCoverage = async () => {
    if (!onRefreshAdminCoverage) return;
    setBillingMessage("");
    setCoverageBusy(true);
    try {
      await onRefreshAdminCoverage();
      setBillingMessage("OpenRouter balance refreshed.");
    } catch (e) {
      setBillingMessage(e.message || "Could not refresh OpenRouter balance.");
    } finally {
      setCoverageBusy(false);
    }
  };

  const coverage = adminFinance?.coverage;
  const coverageGuidance = buildCoverageGuidance(coverage);

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
  const billingModal = addBalanceOpen ? (
    <div className="billing-modal-backdrop" role="presentation">
      <div
        className="billing-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="billing-modal-title"
      >
        <div className="billing-modal-header">
          <div>
            <strong id="billing-modal-title">Add Balance</strong>
            <span>Choose an amount, then continue to Stripe.</span>
          </div>
          <button
            type="button"
            className="billing-modal-close"
            onClick={() => setAddBalanceOpen(false)}
            aria-label="Close Add Balance"
          >
            Close
          </button>
        </div>

        <div className="billing-package-list" role="radiogroup" aria-label="Balance amount">
          {topupPackages.map((pkg) => (
            <button
              type="button"
              key={pkg.id}
              role="radio"
              aria-checked={selectedTopup?.id === pkg.id}
              aria-disabled={!packageConfigured(pkg)}
              className={`billing-package-option${selectedTopup?.id === pkg.id ? " selected" : ""}${packageConfigured(pkg) ? "" : " disabled"}`}
              onClick={() => {
                if (packageConfigured(pkg)) setSelectedTopupId(pkg.id);
              }}
              disabled={!packageConfigured(pkg)}
            >
              <strong>{pkg.label}</strong>
              <span>
                {questionFitCopy(pkg, councilProfiles)}
                {!packageConfigured(pkg) ? ` ${pkg.status_label || "Needs Stripe price"}.` : ""}
              </span>
              {!packageConfigured(pkg) ? (
                <em className="warn">Needs price</em>
              ) : pkg.test ? (
                <em>Test</em>
              ) : pkg.recommended ? (
                <em>Recommended</em>
              ) : null}
            </button>
          ))}
        </div>

        <div className="billing-modal-actions">
          <button
            type="button"
            className="settings-cancel-btn"
            onClick={() => setAddBalanceOpen(false)}
            disabled={billingBusy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="settings-save-btn"
            onClick={confirmAddBalance}
            disabled={billingBusy || !selectedTopup?.id}
          >
            {billingBusy
              ? "Opening Stripe..."
              : `Continue with ${selectedTopup?.label || "selected amount"}`}
          </button>
        </div>
      </div>
    </div>
  ) : null;

  const settingsActionDialog =
    settingsDialog === "model-access" ? (
      <div
        className="settings-modal-backdrop"
        role="presentation"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) setSettingsDialog(null);
        }}
      >
        <div
          className="settings-action-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="model-access-title"
        >
          <div className="settings-action-modal-header">
            <div>
              <span className="settings-overline">Model access</span>
              <h3 id="model-access-title">OpenRouter key</h3>
              <p>
                LLM Council uses this key server-side for your account. Model
                costs stay on your OpenRouter account.
              </p>
            </div>
            <button
              type="button"
              className="settings-modal-close"
              onClick={() => setSettingsDialog(null)}
              aria-label="Close model access"
            >
              Close
            </button>
          </div>

          <div className="settings-modal-status-row">
            <span
              className={`settings-status-badge${openRouterStatus?.configured ? " ready" : " warn"}`}
            >
              {openRouterStatus?.configured ? "Ready" : "Needs key"}
            </span>
            <span>
              {openRouterStatus?.configured
                ? openRouterStatus.source === "environment"
                  ? "Configured for this account"
                  : `Saved (${openRouterStatus.masked_key})`
                : "No key saved"}
            </span>
          </div>

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

          <div className="settings-modal-link-row">
            <a
              href="https://openrouter.ai/settings/keys"
              target="_blank"
              rel="noreferrer"
            >
              Create an OpenRouter key
            </a>
            <a
              href="https://openrouter.ai/docs/api-reference/authentication"
              target="_blank"
              rel="noreferrer"
            >
              How keys are used
            </a>
          </div>

          {openRouterStatusMessage && (
            <div
              className={`account-status${openRouterStatusMessage.includes("saved") || openRouterStatusMessage.includes("cleared") ? " success" : ""}`}
            >
              {openRouterStatusMessage}
            </div>
          )}

          <div className="settings-modal-actions">
            <button
              type="button"
              className="settings-primary-action"
              onClick={submitOpenRouterKey}
              disabled={openRouterBusy || !openRouterKey.trim()}
            >
              {openRouterBusy ? "Saving..." : "Save key"}
            </button>
            <button
              type="button"
              className="settings-secondary-action"
              onClick={clearOpenRouterKey}
              disabled={openRouterBusy || openRouterStatus?.source !== "account"}
            >
              Clear key
            </button>
          </div>

          {openRouterStatus?.configured && (
            <button
              type="button"
              className="settings-secondary-action wide"
              onClick={() => updateBillingMode("byok")}
              disabled={billingBusy}
            >
              Use this key for runs
            </button>
          )}
        </div>
      </div>
    ) : null;

  return (
    <>
      <div
        className={`sidebar ${isOpen ? "open" : ""} ${isPinned ? "pinned" : ""} ${showSettings ? "settings-fullpanel" : ""}`}
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
            {auth?.role === "owner" && (
              <div className="settings-view-tabs" role="tablist" aria-label="Settings views">
                <button
                  type="button"
                  role="tab"
                  aria-selected={settingsView === "settings"}
                  className={settingsView === "settings" ? "selected" : ""}
                  onClick={() => setSettingsView("settings")}
                >
                  Settings
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={settingsView === "admin"}
                  className={settingsView === "admin" ? "selected" : ""}
                  onClick={() => setSettingsView("admin")}
                >
                  Owner Admin
                </button>
              </div>
            )}

            {settingsView === "admin" && auth?.role === "owner" ? (
              <>
                <div className="settings-subtitle settings-account-subtitle">
                  <span>Owner Admin</span>
                  <span className="settings-chairman-hint">
                    {coverage?.status || "No coverage snapshot"}
                  </span>
                </div>
                <div className="integration-settings-card admin-coverage-card">
                  <div className="admin-coverage-head">
                    <div>
                      <span className="settings-overline">OpenRouter target</span>
                      <strong className={`admin-coverage-headline admin-coverage-headline--${coverageGuidance.tone}`}>
                        {coverageGuidance.headline}
                      </strong>
                    </div>
                    <button
                      type="button"
                      className="settings-secondary-action compact admin-coverage-refresh"
                      onClick={refreshCoverage}
                      disabled={coverageBusy || billingBusy}
                    >
                      {coverageBusy ? "Refreshing..." : "Refresh"}
                    </button>
                  </div>
                  <div className="admin-finance-grid admin-coverage-grid">
                    <div>
                      <span>OpenRouter available</span>
                      <strong>
                        {coverage?.available_credits_usd != null
                          ? formatUsd(coverage.available_credits_usd)
                          : "—"}
                      </strong>
                    </div>
                    <div>
                      <span>Target floor</span>
                      <strong>
                        {coverage?.required_floor_usd != null
                          ? formatUsd(coverage.required_floor_usd)
                          : "—"}
                      </strong>
                    </div>
                    <div>
                      <span>Safety buffer</span>
                      <strong>
                        {coverage?.operating_buffer_usd != null
                          ? formatUsd(coverage.operating_buffer_usd)
                          : "—"}
                      </strong>
                    </div>
                    <div>
                      <span>Coverage ratio</span>
                      <strong>
                        {coverage?.coverage_ratio != null
                          ? `${Number(coverage.coverage_ratio).toFixed(2)}x`
                          : "—"}
                      </strong>
                    </div>
                  </div>
                  <p className={`admin-coverage-action admin-coverage-action--${coverageGuidance.tone}`}>
                    {coverageGuidance.action}
                  </p>
                </div>
                <div className="integration-settings-card admin-finance-card">
                  <div className="admin-finance-grid">
                    <div>
                      <span>Outstanding balance</span>
                      <strong>{formatUsd(adminFinance?.app_credits_outstanding_usd)}</strong>
                    </div>
                    <div>
                      <span>Provider reserve</span>
                      <strong>{formatUsd(adminFinance?.managed_raw_liability_usd)}</strong>
                    </div>
                    <div>
                      <span>Payment alerts</span>
                      <strong>{adminFinance?.failed_webhooks_count || 0}</strong>
                    </div>
                    <div>
                      <span>Balance runs</span>
                      <strong>{adminFinance?.managed_mode_paused ? "Paused" : "Allowed"}</strong>
                    </div>
                  </div>
                  <div className="account-actions integration-actions">
                    <button
                      type="button"
                      className="settings-cancel-btn account-logout-btn"
                      onClick={() => toggleManagedPause(true)}
                      disabled={billingBusy || adminFinance?.managed_mode_paused}
                    >
                      Pause balance runs
                    </button>
                    <button
                      type="button"
                      className="settings-save-btn account-password-btn"
                      onClick={() => toggleManagedPause(false)}
                      disabled={billingBusy || !adminFinance?.managed_mode_paused}
                    >
                      Resume
                    </button>
                  </div>
                  {billingMessage && (
                    <div
                      className={`account-status${billingMessage.includes("resumed") || billingMessage.includes("paused") ? " success" : ""}`}
                    >
                      {billingMessage}
                    </div>
                  )}
                </div>

                <div className="settings-subtitle settings-account-subtitle">
                  <span>User Balances</span>
                  <span className="settings-chairman-hint">
                    {(adminFinance?.users_by_balance || []).length} accounts
                  </span>
                </div>
                <div className="integration-settings-card admin-finance-card">
                  {(adminFinance?.users_by_balance || []).length > 0 ? (
                    <div className="admin-balance-list">
                      {(adminFinance?.users_by_balance || []).slice(0, 12).map((user) => (
                        <div className="admin-balance-row" key={user.user_id}>
                          <div>
                            <strong>{user.user_id}</strong>
                            <span>
                              Available {formatUsd(user.available_balance_usd)}
                              {Number(user.reserved_balance_usd || 0) > 0
                                ? `, ${formatUsd(user.reserved_balance_usd)} held`
                                : ""}
                            </span>
                          </div>
                          <strong>{formatUsd(user.balance)}</strong>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="billing-note">No account balances yet.</p>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="settings-hub">
                  <section className="settings-primary-card settings-balance-card">
                    <div>
                      <span className="settings-overline">LLM Council Balance</span>
                      <h3>{formatUsd(availableBalance)} available</h3>
                      <p>{balanceSummary}</p>
                    </div>
                    <span
                      className={`settings-status-badge${canAddBalance ? " ready" : " warn"}`}
                    >
                      {balanceStatusLabel}
                    </span>
                    <div className="settings-balance-actions">
                      <button
                        type="button"
                        className="settings-primary-action"
                        onClick={openAddBalance}
                        disabled={!canAddBalance || billingBusy}
                      >
                        Add balance
                      </button>
                      {canUseManagedBalance && (
                        <button
                          type="button"
                          className="settings-secondary-action"
                          onClick={() => updateBillingMode("managed")}
                          disabled={billingBusy || managedBalanceActive}
                        >
                          {managedBalanceModeLabel}
                        </button>
                      )}
                    </div>
                    {billingStatusError && (
                      <div className="account-status">{billingStatusError}</div>
                    )}
                    {billingMessage && (
                      <div
                        className={`account-status${billingMessage.includes("updated") || billingMessage.includes("used") || billingMessage.includes("saved") || billingMessage.includes("will be used") ? " success" : ""}`}
                      >
                        {billingMessage}
                      </div>
                    )}
                    {billingNotice && (
                      <div
                        className={`account-status${billingNotice.type === "success" || billingNotice.type === "info" ? " success" : ""}`}
                      >
                        {billingNotice.message}
                      </div>
                    )}
                  </section>

                  <section
                    className={`settings-primary-card${openRouterStatus?.configured ? "" : " needs-action"}`}
                    ref={integrationCardRef}
                  >
                    <div>
                      <span className="settings-overline">Model access</span>
                      <h3>
                        {openRouterStatus?.configured
                          ? "OpenRouter connected"
                          : "Add your OpenRouter key"}
                      </h3>
                      <p>
                        {openRouterStatus?.configured
                          ? "Runs use your OpenRouter account."
                          : "Required before your first council run."}
                      </p>
                    </div>
                    <span
                      className={`settings-status-badge${openRouterStatus?.configured ? " ready" : " warn"}`}
                    >
                      {openRouterStatus?.configured ? "Ready" : "Needs key"}
                    </span>
                    <button
                      type="button"
                      className="settings-primary-action"
                      onClick={() => setSettingsDialog("model-access")}
                    >
                      {openRouterStatus?.configured ? "Manage key" : "Add key"}
                    </button>
                  </section>

                  <button
                    type="button"
                    className="settings-clean-row"
                    onClick={openCouncilSetup}
                  >
                    <span>
                      <strong>Council</strong>
                      <small>
                        {councilModelCount} model{councilModelCount === 1 ? "" : "s"}
                        {" "}· Chair: {chairmanLabel}
                      </small>
                    </span>
                    <em>Edit</em>
                  </button>

                  <div className="settings-clean-row settings-theme-row">
                    <span>
                      <strong>Theme</strong>
                      <small>{draftThemeMode[0].toUpperCase() + draftThemeMode.slice(1)}</small>
                    </span>
                    <div className="settings-theme-switch" role="group" aria-label="Theme mode">
                      {["light", "dark", "system"].map((mode) => (
                        <button
                          key={mode}
                          type="button"
                          className={draftThemeMode === mode ? "selected" : ""}
                          onClick={() => selectThemeMode(mode)}
                          aria-pressed={draftThemeMode === mode}
                        >
                          {mode[0].toUpperCase() + mode.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="settings-account-row">
                    <span>
                      <strong>{auth?.email || "Google account"}</strong>
                      <small>Signed in with Google</small>
                    </span>
                    <button
                      type="button"
                      className="settings-secondary-action compact"
                      onClick={() => {
                        setShowSettings(false);
                        setSettingsDialog(null);
                        onLogout?.();
                      }}
                    >
                      <LogOut size={15} />
                      Sign out
                    </button>
                  </div>
                </div>
              </>
            )}
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
              <button
                type="button"
                className={`sidebar-drawer-pin${isPinned ? " active" : ""}`}
                onClick={onToggleSidebarPin}
                aria-label={isPinned ? "Unpin conversations drawer" : "Pin conversations drawer open"}
                aria-pressed={isPinned}
                title={isPinned ? "Unpin drawer" : "Pin drawer open"}
              >
                <Pin size={15} aria-hidden="true" />
              </button>
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
          </div>
        </>
      )}
      </div>
      {billingModal ? createPortal(billingModal, document.body) : null}
      {settingsActionDialog ? createPortal(settingsActionDialog, document.body) : null}
    </>
  );
}
