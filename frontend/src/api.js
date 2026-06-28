/**
 * API client for the LLM Council backend.
 */

const appBase = import.meta.env.BASE_URL || '/';
const API_BASE = appBase === '/' ? '' : appBase.replace(/\/$/, '');

export const api = {
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to list conversations');
    return response.json();
  },

  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!response.ok) throw new Error('Failed to create conversation');
    return response.json();
  },

  async getSettings() {
    const response = await fetch(`${API_BASE}/api/settings`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to load settings');
    return response.json();
  },

  async updateSettings(payload) {
    const response = await fetch(`${API_BASE}/api/settings`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error('Failed to update settings');
    return response.json();
  },

  async getModelStatus() {
    const response = await fetch(`${API_BASE}/api/models/status`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to load model status');
    return response.json();
  },

  async getOpenRouterIntegration() {
    const response = await fetch(`${API_BASE}/api/integrations/openrouter`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to load OpenRouter integration');
    return response.json();
  },

  async updateOpenRouterIntegration(payload) {
    const response = await fetch(`${API_BASE}/api/integrations/openrouter`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to update OpenRouter integration');
    }
    return response.json();
  },

  async getBillingStatus() {
    const response = await fetch(`${API_BASE}/api/billing/status`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to load billing status');
    return response.json();
  },

  async updateBillingMode(billingMode) {
    const response = await fetch(`${API_BASE}/api/billing/mode`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ billing_mode: billingMode }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to update billing mode');
    }
    return response.json();
  },

  async createBillingCheckout(packageId) {
    const response = await fetch(`${API_BASE}/api/billing/checkout`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ package_id: packageId }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to start checkout');
    }
    return response.json();
  },

  async getCouncilProfiles() {
    const response = await fetch(`${API_BASE}/api/council/profiles`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to load council profiles');
    return response.json();
  },

  async estimateCouncilProfile({ content, profileSlug }) {
    const response = await fetch(`${API_BASE}/api/council/estimate`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, profile_slug: profileSlug }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to estimate managed run');
    }
    return response.json();
  },

  async getAdminFinanceOverview() {
    const response = await fetch(`${API_BASE}/api/admin/finance/overview`, { credentials: 'include' });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to load finance overview');
    }
    return response.json();
  },

  async setManagedModePaused(paused) {
    const response = await fetch(`${API_BASE}/api/admin/managed-mode/${paused ? 'pause' : 'resume'}`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to update managed mode');
    }
    return response.json();
  },

  async getModelCatalog(params = {}) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        search.set(key, value);
      }
    });
    const suffix = search.toString() ? `?${search.toString()}` : '';
    const response = await fetch(`${API_BASE}/api/models/catalog${suffix}`, { credentials: 'include' });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to load model catalog');
    }
    return response.json();
  },

  async getLatestModelCuration() {
    const response = await fetch(`${API_BASE}/api/model-curation/latest`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to load model curation status');
    return response.json();
  },

  async runModelCuration() {
    const response = await fetch(`${API_BASE}/api/model-curation/run`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to run model curation');
    }
    return response.json();
  },

  async approveModelCuration(draftId) {
    const response = await fetch(`${API_BASE}/api/model-curation/${draftId}/approve`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to approve model curation');
    }
    return response.json();
  },

  async getConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to get conversation');
    return response.json();
  },

  async pinConversation(conversationId, pinned) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/pin`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned }),
    });
    if (!response.ok) throw new Error('Failed to pin conversation');
    return response.json();
  },

  async deleteConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok) throw new Error('Failed to delete conversation');
    return response.json();
  },

  async createRun(conversationId, content, options = {}) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/runs`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        billing_mode: options.billingMode,
        profile_slug: options.profileSlug,
      }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to create run');
    }
    return response.json();
  },

  async improvePrompt(content) {
    const response = await fetch(`${API_BASE}/api/prompt/improve`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to improve question');
    }
    return response.json();
  },

  async getRun(conversationId, runId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/runs/${runId}`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to get run');
    return response.json();
  },

  async getActiveRun(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/runs/active`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to get active run');
    return response.json();
  },

  async stopRun(conversationId, runId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/runs/${runId}/stop`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!response.ok) throw new Error('Failed to stop run');
    return response.json();
  },

  async waitForRun(conversationId, runId, onUpdate, intervalMs = 700) {
    let done = false;
    while (!done) {
      const run = await this.getRun(conversationId, runId);
      onUpdate(run);
      done = run.status === 'complete' || run.status === 'failed' || run.status === 'canceled';
      if (!done) {
        await new Promise((resolve) => setTimeout(resolve, intervalMs));
      }
    }
  },

  // Legacy APIs kept for compatibility
  async sendMessage(conversationId, content) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/message`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) throw new Error('Failed to send message');
    return response.json();
  },

  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/message/stream`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type || 'snapshot', event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  async getAuthMe() {
    const response = await fetch(`${API_BASE}/api/auth/me`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to check auth status');
    return response.json();
  },

  async login(email, password) {
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Login failed');
    }
    return response.json();
  },

  loginWithGoogle() {
    window.location.assign(`${API_BASE}/api/auth/oauth/google/start`);
  },

  async signup({ name, email, password, openRouterApiKey }) {
    const response = await fetch(`${API_BASE}/api/auth/signup`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        email,
        password,
        openrouter_api_key: openRouterApiKey,
      }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Account creation failed');
    }
    return response.json();
  },

  async logout() {
    const response = await fetch(`${API_BASE}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!response.ok) throw new Error('Failed to log out');
    return response.json();
  },

  async changePassword(currentPassword, newPassword) {
    const response = await fetch(`${API_BASE}/api/auth/change-password`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to change password');
    }
    return response.json();
  },

  async resetPassword(email, resetToken, newPassword) {
    const response = await fetch(`${API_BASE}/api/auth/reset-password`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        reset_token: resetToken,
        new_password: newPassword,
      }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to reset password');
    }
    return response.json();
  },
};
