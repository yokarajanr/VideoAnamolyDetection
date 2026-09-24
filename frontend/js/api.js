/**
 * js/api.js — Centralized API client for the Surveillance Platform backend.
 * All fetch calls go through this module for consistent error handling and
 * base URL management.
 */

const API = (() => {
  const getBaseUrl = () => {
    const wsUrl = localStorage.getItem('backend_url') || 'http://localhost:8000';
    return wsUrl.replace(/^ws/, 'http');
  };

  const getWsUrl = () => {
    const stored = localStorage.getItem('backend_url') || 'ws://localhost:8000';
    return stored.replace(/^http/, 'ws');
  };

  async function request(path, options = {}) {
    const url = `${getBaseUrl()}${path}`;
    try {
      const res = await fetch(url, {
        ...options,
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (e) {
      if (e.name === 'TypeError') throw new Error(`Cannot reach backend at ${url}`);
      throw e;
    }
  }

  return {
    getWsUrl,
    getBaseUrl,

    // Health
    health: () => request('/api/health'),

    // Events
    getEvents: (params = {}) => {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([_, v]) => v != null && v !== ''))
      ).toString();
      return request(`/api/events${qs ? '?' + qs : ''}`);
    },
    getStats:  () => request('/api/events/stats'),
    getRecent: (n = 20) => request(`/api/events/recent?limit=${n}`),
    getEvent:  (id) => request(`/api/events/${id}`),
    deleteEvent: (id) => request(`/api/events/${id}`, { method: 'DELETE' }),
    deleteEvents: (ids) => request('/api/events/bulk-delete', { method: 'POST', body: JSON.stringify({ event_ids: ids }) }),

    // RAG
    query: (body) => request('/api/rag/query', { method: 'POST', body: JSON.stringify(body) }),
    summary: () => request('/api/rag/summary'),
    presets: () => request('/api/rag/presets'),

    // Zones
    // Zones
    getZones:    (source = 'live') => request(`/api/zones?source=${source}`),
    createZone:  (z) => request('/api/zones', { method: 'POST', body: JSON.stringify(z) }),
    deleteZone:  (id) => request(`/api/zones/${id}`, { method: 'DELETE' }),
    clearZones:  (source = 'live') => request(`/api/zones?source=${source}`, { method: 'DELETE' }),

    // Environment
    getEnvironment: () => request('/api/environment'),
    listEnvironments: () => request('/api/environment/list'),
    setEnvironment: (key) => request('/api/environment', {
      method: 'POST',
      body: JSON.stringify({ environment_key: key }),
    }),
    getEnvProfile: (key) => request(`/api/environment/${key}/profile`),
  };
})();
