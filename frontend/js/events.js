/**
 * js/events.js — Event history page: table rendering, filters, pagination, modal.
 */

let eventsPage = 0;
const eventsPageSize = 25;
let eventsTotalPages = 1;
let allEnvs = new Set();

async function loadEvents() {
  const params = {
    query: document.getElementById('filter-search')?.value || '',
    risk_level: document.getElementById('filter-risk')?.value || '',
    environment: document.getElementById('filter-env')?.value || '',
    from_date: document.getElementById('filter-from')?.value || '',
    to_date: document.getElementById('filter-to')?.value || '',
    limit: eventsPageSize,
    offset: eventsPage * eventsPageSize,
  };

  try {
    const [evData, statsData] = await Promise.all([
      API.getEvents(params),
      API.getStats(),
    ]);

    renderEventsTable(evData.events || []);
    updateEventsPagination(evData.total || 0, evData.offset || 0);
    updateEventsStats(statsData);

    // Collect environments for filter dropdown
    (evData.events || []).forEach(e => allEnvs.add(e.environment));
    populateEnvFilter();
  } catch (err) {
    console.error('Failed to load events:', err);
  }
}

function renderEventsTable(events) {
  const tbody = document.getElementById('events-tbody');
  document.getElementById('events-count-tag').textContent = `${events.length} events`;

  if (!events.length) {
    tbody.innerHTML = `<tr><td colspan="7">
      <div class="empty-state"><div class="icon">📋</div><p>No events match your filters.</p></div>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = events.map(ev => {
    const risk = (ev.risk_level || 'Low').toLowerCase();
    const ts = new Date(ev.timestamp).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
    const objects = (ev.objects_detected || []).slice(0, 3).join(', ') || '—';
    const anomBadge = ev.is_anomalous ? '<span class="tag" style="background:var(--risk-high-dim);color:var(--risk-high);border-color:rgba(255,82,82,0.2)">⚠ Anomaly</span>' : '';

    return `
      <tr onclick="showEventModal('${ev.id}')" style="cursor:pointer">
        <td onclick="event.stopPropagation()"><input type="checkbox" class="event-checkbox" value="${ev.id}" onchange="updateDeleteSelectedButton()"></td>
        <td class="font-mono" style="font-size:11px;color:var(--text-muted)">${ts}</td>
        <td>${ev.environment || '—'}</td>
        <td>
          <div>${ev.event_type || '—'}</div>
          ${anomBadge}
        </td>
        <td><span class="risk-pill ${risk}">${ev.risk_level}</span></td>
        <td class="text-sm text-muted truncate" style="max-width:140px">${objects}</td>
        <td>
          <div style="display:flex;gap:4px">
            <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();showEventModal('${ev.id}')">Detail →</button>
            <button class="btn btn-ghost btn-sm" style="color:var(--risk-high);padding:4px" onclick="event.stopPropagation();deleteEvent('${ev.id}')">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
            </button>
          </div>
        </td>
      </tr>`;
  }).join('');
}

function updateEventsStats(stats) {
  document.getElementById('hist-total').textContent = stats.total || 0;
  document.getElementById('hist-critical').textContent = stats.by_risk?.Critical || 0;
  document.getElementById('hist-high').textContent = stats.by_risk?.High || 0;
  document.getElementById('hist-today').textContent = stats.anomalies_today || 0;
}

function updateEventsPagination(total, offset) {
  eventsTotalPages = Math.ceil(total / eventsPageSize) || 1;
  document.getElementById('pagination-info').textContent =
    `Showing ${offset + 1}–${Math.min(offset + eventsPageSize, total)} of ${total} events`;
  document.getElementById('btn-prev').disabled = eventsPage <= 0;
  document.getElementById('btn-next').disabled = eventsPage >= eventsTotalPages - 1;
}

function changePage(dir) {
  eventsPage = Math.max(0, Math.min(eventsPage + dir, eventsTotalPages - 1));
  loadEvents();
}

function filterEvents() {
  eventsPage = 0;
  loadEvents();
}

function clearFilters() {
  document.getElementById('filter-search').value = '';
  document.getElementById('filter-risk').value = '';
  document.getElementById('filter-env').value = '';
  document.getElementById('filter-from').value = '';
  document.getElementById('filter-to').value = '';
  eventsPage = 0;
  loadEvents();
}

function populateEnvFilter() {
  const sel = document.getElementById('filter-env');
  const current = sel.value;
  const options = ['<option value="">All Environments</option>'];
  allEnvs.forEach(e => {
    options.push(`<option value="${e}" ${current === e ? 'selected' : ''}>${e}</option>`);
  });
  sel.innerHTML = options.join('');
}

async function showEventModal(id) {
  try {
    const ev = await API.getEvent(id);
    const body = document.getElementById('event-modal-body');
    const risk = (ev.risk_level || 'Low').toLowerCase();
    const ts = new Date(ev.timestamp).toLocaleString('en-IN', {
      weekday: 'short', day: '2-digit', month: 'long', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });

    const zoneViolations = (ev.zone_violations || []).length
      ? `<div style="margin-top:14px"><div class="card-title" style="margin-bottom:6px">Zone Violations</div>${ev.zone_violations.map(z => `<span class="tag" style="background:var(--risk-high-dim);color:var(--risk-high)">${z}</span>`).join(' ')}</div>`
      : '';

    const snapshot = ev.frame_snapshot
      ? `<img src="data:image/jpeg;base64,${ev.frame_snapshot}" style="width:100%;border-radius:8px;margin-bottom:16px;border:1px solid var(--border)" alt="Event frame"/>`
      : '';

    body.innerHTML = `
      ${snapshot}
      <div class="flex items-center gap-3" style="margin-bottom:16px">
        <span class="risk-pill ${risk}">${ev.risk_level}</span>
        <span class="tag">${ev.environment}</span>
        <span class="tag">${ev.event_type}</span>
        ${ev.is_anomalous ? '<span class="tag" style="background:var(--risk-high-dim);color:var(--risk-high)">⚠ Anomaly</span>' : ''}
      </div>
      <div class="font-mono text-xs text-muted" style="margin-bottom:16px">${ts} · ID: ${ev.id}</div>

      <div style="margin-bottom:14px">
        <div class="card-title" style="margin-bottom:6px">Description</div>
        <div style="font-size:13px;color:var(--text-secondary);line-height:1.65">${ev.description || '—'}</div>
      </div>

      <div style="margin-bottom:14px">
        <div class="card-title" style="margin-bottom:6px">Reasoning</div>
        <div style="font-size:12.5px;color:var(--text-muted);line-height:1.65">${ev.reasoning || '—'}</div>
      </div>

      <div style="margin-bottom:14px">
        <div class="card-title" style="margin-bottom:6px">Recommended Action</div>
        <div style="font-size:13px;color:var(--accent)">${ev.recommended_action || '—'}</div>
      </div>

      ${ev.objects_detected?.length ? `
      <div style="margin-bottom:14px">
        <div class="card-title" style="margin-bottom:6px">Detected Objects</div>
        <div class="flex gap-2" style="flex-wrap:wrap">${ev.objects_detected.map(o => `<span class="tag">${o}</span>`).join('')}</div>
      </div>` : ''}

      ${zoneViolations}
    `;

    openModal();
  } catch (err) {
    console.error('Failed to load event:', err);
  }
}

function openModal() {
  document.getElementById('event-modal').classList.add('open');
}

function closeModal() {
  document.getElementById('event-modal').classList.remove('open');
}

// Close modal on overlay click
document.addEventListener('click', e => {
  if (e.target.id === 'event-modal') closeModal();
});

async function deleteEvent(id) {
  if (!confirm('Are you sure you want to delete this event?')) return;
  try {
    await API.deleteEvent(id);
    loadEvents();
  } catch (err) {
    alert('Failed to delete event: ' + err.message);
  }
}

function toggleAllEvents(source) {
  const checkboxes = document.querySelectorAll('.event-checkbox');
  checkboxes.forEach(cb => cb.checked = source.checked);
  updateDeleteSelectedButton();
}

function updateDeleteSelectedButton() {
  const checked = document.querySelectorAll('.event-checkbox:checked').length;
  const btn = document.getElementById('btn-delete-selected');
  if (checked > 0) {
    btn.style.display = 'inline-flex';
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-trash-2" style="margin-right:4px;vertical-align:-2px"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg> Delete Selected (${checked})`;
  } else {
    btn.style.display = 'none';
  }
}

async function deleteSelectedEvents() {
  const checkboxes = document.querySelectorAll('.event-checkbox:checked');
  const ids = Array.from(checkboxes).map(cb => cb.value);
  if (ids.length === 0) return;
  if (!confirm(`Are you sure you want to delete ${ids.length} events?`)) return;
  
  try {
    await API.deleteEvents(ids);
    document.getElementById('selectAllCheckbox').checked = false;
    updateDeleteSelectedButton();
    loadEvents();
  } catch (err) {
    alert('Failed to delete events: ' + err.message);
  }
}
