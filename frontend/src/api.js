/**
 * API client for the LLM Council backend.
 */

const API_BASE = '';

export const api = {
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) throw new Error('Failed to list conversations');
    return response.json();
  },

  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!response.ok) throw new Error('Failed to create conversation');
    return response.json();
  },

  async getSettings() {
    const response = await fetch(`${API_BASE}/api/settings`);
    if (!response.ok) throw new Error('Failed to load settings');
    return response.json();
  },

  async updateSettings(payload) {
    const response = await fetch(`${API_BASE}/api/settings`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error('Failed to update settings');
    return response.json();
  },

  async getConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`);
    if (!response.ok) throw new Error('Failed to get conversation');
    return response.json();
  },

  async pinConversation(conversationId, pinned) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/pin`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned }),
    });
    if (!response.ok) throw new Error('Failed to pin conversation');
    return response.json();
  },

  async deleteConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete conversation');
    return response.json();
  },

  async createRun(conversationId, content) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) throw new Error('Failed to create run');
    return response.json();
  },

  async getRun(conversationId, runId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/runs/${runId}`);
    if (!response.ok) throw new Error('Failed to get run');
    return response.json();
  },

  async getActiveRun(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/runs/active`);
    if (!response.ok) throw new Error('Failed to get active run');
    return response.json();
  },

  async stopRun(conversationId, runId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/runs/${runId}/stop`, {
      method: 'POST',
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) throw new Error('Failed to send message');
    return response.json();
  },

  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/message/stream`, {
      method: 'POST',
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
};
