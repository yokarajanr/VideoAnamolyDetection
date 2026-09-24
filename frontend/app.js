/**
 * app.js — Main application controller.
 *
 * Handles:
 * - Page navigation / routing
 * - Application initialization on load
 * - Environment management
 * - Settings persistence (localStorage)
 * - Toast notification system
 * - Health check
 */

// ── Page Navigation ─────────────────────────────────────────────────────────

const PAGE_CONFIG = {
  live: { title: 'Live Monitor', subtitle: 'Real-time surveillance feed', id: 'page-live' },
  'test-video': { title: 'Test Video', subtitle: 'Simulate anomalies with local video files', id: 'page-test-video' },
  events: { title: 'Event History', subtitle: 'Searchable anomaly and event log', id: 'page-events' },
  rag: { title: 'Surveillance AI', subtitle: 'RAG-powered natural language memory query', id: 'page-rag' },
  settings: { title: 'Settings', subtitle: 'Environment, zones, and system configuration', id: 'page-settings' },
};

let currentPage = 'live';
let currentAnomaliesToday = 0;

function updateEventBadge() {
  const lastSeen = parseInt(localStorage.getItem('lastSeenAnomaliesToday') || '0', 10);
  
  // If the count resets (e.g., new day), reset the last seen
  let unread = currentAnomaliesToday - lastSeen;
  if (unread < 0) {
    localStorage.setItem('lastSeenAnomaliesToday', '0');
    unread = currentAnomaliesToday;
  }
  
  // If currently on events page, mark as read immediately
  if (currentPage === 'events') {
    localStorage.setItem('lastSeenAnomaliesToday', currentAnomaliesToday.toString());
    unread = 0;
  }
  
  const badge = document.getElementById('badge-events');
  if (badge) {
    badge.textContent = unread;
    badge.classList.toggle('visible', unread > 0);
  }
}

function showPage(pageKey, navEl) {
  if (!PAGE_CONFIG[pageKey]) return;
  
  // Stop streams when navigating to a different video source to avoid conflicts
  if (currentPage === 'live' && pageKey === 'test-video') {
      if (typeof stopStream === 'function' && streaming) stopStream();
  } else if (currentPage === 'test-video' && pageKey === 'live') {
      if (typeof stopStream === 'function' && streaming) stopStream();
  }
  
  currentPage = pageKey;

  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

  // Show target page
  document.getElementById(PAGE_CONFIG[pageKey].id).classList.add('active');

  // Update topbar
  document.getElementById('topbar-title').textContent = PAGE_CONFIG[pageKey].title;
  document.getElementById('topbar-subtitle').textContent = PAGE_CONFIG[pageKey].subtitle;

  // Update nav active state
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  if (navEl) navEl.classList.add('active');

  // Page-specific initialization
  if (pageKey === 'events') {
      updateEventBadge();
      loadEvents();
  }
  if (pageKey === 'rag') { loadPresets(); loadDailySummary(); }
  if (pageKey === 'settings') { loadEnvironments(); if (typeof initZoneCanvas === 'function') initZoneCanvas('settings'); }
  if (pageKey === 'test-video') { if (typeof initZoneCanvas === 'function') initZoneCanvas('test'); }
  if (pageKey === 'live') { if (typeof initZoneCanvas === 'function') initZoneCanvas('live'); }
}

// ── Environment Management ───────────────────────────────────────────────────

const SVG_PROPS = 'width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';

const ENV_ICONS = {
  home: `<svg ${SVG_PROPS}><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  farming: `<svg ${SVG_PROPS}><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/></svg>`,
  transportation: `<svg ${SVG_PROPS}><path d="M10 2v20"/><path d="M14 2v20"/><path d="M10 6h4"/><path d="M10 12h4"/><path d="M10 18h4"/></svg>`,
  office: `<svg ${SVG_PROPS}><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/></svg>`,
  classroom: `<svg ${SVG_PROPS}><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>`,
  laboratory: `<svg ${SVG_PROPS}><path d="M10 2v7.52l-7 10.19A2 2 0 0 0 4.66 23h14.68a2 2 0 0 0 1.66-3.29l-7-10.19V2"/><path d="M8 2h8"/><path d="M6 16h12"/></svg>`,
  factory: `<svg ${SVG_PROPS}><path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M17 18h1"/><path d="M12 18h1"/><path d="M7 18h1"/></svg>`,
  warehouse: `<svg ${SVG_PROPS}><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>`,
  parking: `<svg ${SVG_PROPS}><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/></svg>`,
  corridor: `<svg ${SVG_PROPS}><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
  custom: `<svg ${SVG_PROPS}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
};

async function loadEnvironments() {
  try {
    const [envData, listData] = await Promise.all([
      API.getEnvironment(),
      API.listEnvironments(),
    ]);

    renderEnvGrid(listData.environments || [], envData.current);
    renderEnvProfile(envData.profile);
    updateEnvBadge(envData.current, envData.profile?.display_name);
  } catch (e) {
    console.warn('Could not load environments:', e);
  }
}

function renderEnvGrid(environments, current) {
  const grid = document.getElementById('env-grid');
  grid.innerHTML = environments.map(env => `
    <div class="env-card ${env.key === current ? 'active' : ''}"
         onclick="selectEnvironment('${env.key}')"
         title="${env.description}">
      <div class="env-card-icon">${ENV_ICONS[env.key] || '📍'}</div>
      <div class="env-card-name">${env.display_name}</div>
    </div>`).join('');
}

function renderEnvProfile(profile) {
  const el = document.getElementById('env-profile-display');
  if (!profile) { el.textContent = '—'; return; }

  const anomalies = Object.entries(profile.anomalies || {}).slice(0, 6);
  const activities = (profile.expected_activities || []).slice(0, 4);

  el.innerHTML = `
    <strong>${profile.display_name}</strong> — ${profile.description}<br/><br/>
    <strong>Expected activities:</strong> ${activities.join(', ')}<br/><br/>
    <strong>Monitored anomalies:</strong><br/>
    ${anomalies.map(([name, risk]) => {
      const cls = risk.toLowerCase();
      return `<span class="risk-pill ${cls}" style="margin:2px;font-size:10px">${name}</span>`;
    }).join('')}
  `;
}

async function selectEnvironment(key) {
  try {
    const data = await API.setEnvironment(key);
    renderEnvGrid(
      Object.entries(ENV_ICONS).map(([k]) => ({ key: k, display_name: k, description: '' })),
      key
    );
    renderEnvProfile(data.profile);
    updateEnvBadge(key, data.profile?.display_name);
    showToast(`Environment set to ${data.profile?.display_name || key}`, 'success');
    loadEnvironments(); // refresh with correct data
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

function updateEnvBadge(key, displayName) {
  const icon = ENV_ICONS[key] || '📍';
  document.getElementById('env-name-badge').textContent = displayName || key;
}

// ── Settings ─────────────────────────────────────────────────────────────────

function loadSettings() {
  const backendUrl = localStorage.getItem('backend_url') || 'ws://localhost:8000';
  const voiceEnabled = localStorage.getItem('voice_enabled') !== 'false';

  const urlInput = document.getElementById('backend-url');
  if (urlInput) urlInput.value = backendUrl;

  const voiceToggle = document.getElementById('toggle-voice');
  if (voiceToggle) voiceToggle.checked = voiceEnabled;
}

function saveSettings() {
  const backendUrl = document.getElementById('backend-url')?.value?.trim() || 'ws://localhost:8000';
  const voiceEnabled = document.getElementById('toggle-voice')?.checked ?? true;

  localStorage.setItem('backend_url', backendUrl);
  localStorage.setItem('voice_enabled', voiceEnabled);

  showToast('Settings saved! Reconnect for URL changes to take effect.', 'success');
}

// ── Health Check ─────────────────────────────────────────────────────────────

async function checkHealth() {
  const el = document.getElementById('health-display');
  el.innerHTML = '<div class="flex gap-2" style="font-size:12px"><div class="spinner"></div> Checking...</div>';

  try {
    const h = await API.health();
    const components = h.components || {};
    el.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:8px">
        ${Object.entries(components).map(([key, val]) => `
          <div class="flex items-center justify-between" style="font-size:13px">
            <span style="font-weight:500;text-transform:capitalize">${key.replace('_', ' ')}</span>
            <span class="tag" style="background:var(--risk-low-dim);color:var(--risk-low)">${val}</span>
          </div>`).join('')}
        <div class="flex items-center justify-between" style="font-size:13px;margin-top:4px">
          <span>Version</span>
          <span class="tag">${h.version || '1.0.0'}</span>
        </div>
      </div>`;
  } catch (err) {
    el.innerHTML = `
      <div style="color:var(--risk-high);font-size:13px">
        ⚠ Backend not reachable<br/>
        <span style="font-size:11px;color:var(--text-muted)">${err.message}</span><br/><br/>
        <span style="font-size:11px">Make sure the backend is running:</span><br/>
        <code style="font-family:var(--font-mono);font-size:11px;color:var(--accent)">cd backend && uvicorn main:app</code>
      </div>`;
  }
}

// ── Toast Notifications ───────────────────────────────────────────────────────

function showToast(message, type = 'info') {
  const container = getOrCreateToastContainer();

  const toast = document.createElement('div');
  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
  const colors = {
    success: 'var(--risk-low)', error: 'var(--risk-high)',
    warning: 'var(--risk-medium)', info: 'var(--accent)',
  };

  toast.style.cssText = `
    display: flex; align-items: center; gap: 10px;
    padding: 12px 16px;
    background: var(--bg-secondary); border: 1px solid var(--border);
    border-radius: 10px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    font-size: 13px; font-family: var(--font-base); color: var(--text-primary);
    border-left: 3px solid ${colors[type]};
    animation: slide-in-toast 0.3s ease;
    max-width: 360px; min-width: 200px;
  `;

  toast.innerHTML = `
    <span style="color:${colors[type]};font-size:15px">${icons[type]}</span>
    <span style="flex:1">${message}</span>
  `;

  const style = document.createElement('style');
  style.textContent = `@keyframes slide-in-toast{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}`;
  document.head.appendChild(style);

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function getOrCreateToastContainer() {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = `
      position: fixed; bottom: 24px; right: 24px;
      display: flex; flex-direction: column; gap: 10px;
      z-index: 9999; pointer-events: none;
    `;
    document.body.appendChild(container);
  }
  return container;
}

// ── Periodic Updates ──────────────────────────────────────────────────────────

async function periodicUpdate() {
  try {
    const stats = await API.getStats();
    document.getElementById('event-count-sidebar').textContent =
      `${stats.total || 0} events stored`;

    // Update badge if we have new events
    const total = stats.total || 0;
    if (total > 0) {
      currentAnomaliesToday = stats.anomalies_today || 0;
      updateEventBadge();
    }
  } catch (e) {
    // Silently fail if backend not connected
  }
}

// ── App Initialization ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  loadEnvironments().catch(() => {}); // non-blocking

  // Periodic stats refresh every 30s
  setInterval(periodicUpdate, 30_000);
  periodicUpdate();

  // Keyboard shortcut: Enter to send chat
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  console.log(
    '%c 🛡️ SurveillanceAI Platform',
    'color:#00d4ff;font-size:18px;font-weight:bold;'
  );
  console.log('%c Hybrid YOLO·VLM·RAG Architecture', 'color:#9aa0a6');
});
