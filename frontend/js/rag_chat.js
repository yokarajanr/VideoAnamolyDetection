/**
 * js/rag_chat.js — Surveillance AI RAG chat interface.
 *
 * Sends natural language questions to the backend RAG endpoint,
 * renders AI responses with source event citations, and loads
 * preset query shortcuts.
 */

let chatHistory = [];

async function loadPresets() {
  try {
    const data = await API.presets();
    const container = document.getElementById('preset-chips');
    container.innerHTML = (data.presets || []).map(p => `
      <div class="preset-chip" onclick="usePreset('${escHtml(p.query)}', '${escHtml(p.date_filter || '')}')">
        ${p.label}
      </div>`).join('');
  } catch (e) {
    console.warn('Could not load presets:', e);
  }
}

async function loadDailySummary() {
  const el = document.getElementById('daily-summary');
  el.textContent = 'Generating summary...';
  try {
    const data = await API.summary();
    // Render markdown-like formatting
    el.innerHTML = markdownToHtml(data.summary || 'No summary available.');
  } catch (e) {
    el.textContent = 'Could not load summary. Make sure the backend is running.';
  }
}

function usePreset(query, dateFilter) {
  document.getElementById('chat-input').value = query;
  sendChatMessage(dateFilter || null);
}

async function sendChatMessage(dateFilter = null) {
  const input = document.getElementById('chat-input');
  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  appendMessage('user', question);

  // Show typing indicator
  const typingId = 'typing-' + Date.now();
  appendTypingIndicator(typingId);

  const btn = document.getElementById('btn-send');
  btn.disabled = true;
  document.getElementById('send-icon').textContent = '⏳';

  try {
    const body = {
      question,
      max_context_events: 8,
      date_filter: dateFilter,
    };

    const res = await API.query(body);
    removeTypingIndicator(typingId);
    appendMessage('ai', res.answer || 'No response.');

    // Show source events
    renderSourceEvents(res.source_events || [], res.context_used || 0);

    chatHistory.push({ question, answer: res.answer });

  } catch (err) {
    removeTypingIndicator(typingId);
    appendMessage('ai', `⚠️ Error: ${err.message}. Make sure the backend is running and your API keys are configured.`);
  } finally {
    btn.disabled = false;
    document.getElementById('send-icon').textContent = '➤';
  }
}

function appendMessage(role, text) {
  const container = document.getElementById('chat-messages');
  const isUser = role === 'user';

  const div = document.createElement('div');
  div.className = `chat-message ${role}`;
  div.innerHTML = `
    <div class="chat-avatar">${isUser ? '👤' : '🛡️'}</div>
    <div class="chat-bubble">${markdownToHtml(text)}</div>
  `;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendTypingIndicator(id) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-message ai';
  div.id = id;
  div.innerHTML = `
    <div class="chat-avatar">🛡️</div>
    <div class="chat-bubble" style="display:flex;align-items:center;gap:8px">
      <div class="spinner"></div>
      <span style="color:var(--text-muted)">Analyzing surveillance memory...</span>
    </div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator(id) {
  document.getElementById(id)?.remove();
}

function renderSourceEvents(events, count) {
  document.getElementById('retrieved-count').textContent = `${count} events`;
  const el = document.getElementById('source-events-list');

  if (!events.length) {
    el.innerHTML = '<div style="font-size:12px;color:var(--text-muted)">No source events retrieved.</div>';
    return;
  }

  el.innerHTML = events.slice(0, 6).map(ev => {
    const risk = ((ev.risk_level || 'low')).toLowerCase();
    const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
    }) : 'Unknown time';
    return `
      <div class="timeline-item ${risk}" style="font-size:11.5px">
        <div>
          <div style="font-weight:600;margin-bottom:2px">${ev.event_type || 'Event'}</div>
          <div style="color:var(--text-muted)">${ts} · ${ev.environment || '?'}</div>
        </div>
        <span class="risk-pill ${risk}" style="font-size:10px">${ev.risk_level || '?'}</span>
      </div>`;
  }).join('');
}

/** Very lightweight markdown → HTML renderer for chat bubbles. */
function markdownToHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')   // XSS safe
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
    .replace(/^• (.+)$/gm, '• $1')
    .replace(/^## (.+)$/gm, '<strong style="font-size:14px">$1</strong>');
}

function escHtml(str) {
  return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}
