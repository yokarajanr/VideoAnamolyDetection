/**
 * js/stream.js — WebSocket live video stream handler.
 *
 * Architecture (smooth, no stutter):
 *  - <video> element shows raw webcam at native camera FPS (30fps, always smooth)
 *  - A hidden <canvas> captures frames and sends them to the backend
 *  - The overlay <canvas> draws ONLY bounding boxes + zone outlines + risk text
 *    from the JSON data returned by the backend (no full JPEG replacement)
 *  - requestAnimationFrame renders annotations at display FPS
 *
 * This eliminates the frame-toggle stutter completely.
 */

let wsSocket = null;
let streaming = false;
let videoStream = null;
let sendTimer = null;
let fpsTimer = null;
let rafId = null;

// Session counters
let frameCount = 0;
let sessionDetections = 0;
let sessionVlm = 0;
let sessionEvents = 0;

// Latest annotation data from backend (updated whenever backend responds)
let latestAnnotations = {
  detections: [],
  zones: [],
  risk: 'Low',
  riskLabel: 'Low',
  anomalies: [],
  description: '',
  action: '',
  vlmActive: false,
  eventStored: false,
};

// Send a frame every ~100ms (~10fps upload to backend)
const SEND_INTERVAL_MS = 100;

// Hidden canvas for capture (never displayed)
const captureCanvas = document.createElement('canvas');
const captureCtx = captureCanvas.getContext('2d');

const video = () => document.getElementById(currentPage === 'test-video' ? 'test-video-source' : 'video-source');
const overlayCanvas = () => document.getElementById(currentPage === 'test-video' ? 'test-live-canvas' : 'live-canvas');
const placeholder = () => document.getElementById(currentPage === 'test-video' ? 'test-video-placeholder' : 'video-placeholder');
const ui = (id) => document.getElementById(currentPage === 'test-video' ? 'test-' + id : id);

// ── Risk colors ───────────────────────────────────────────────────────────────
const RISK_COLORS = {
  low:      '#00e676',
  medium:   '#ffab40',
  high:     '#ff5252',
  critical: '#ff1744',
};

// ── Camera start / stop ───────────────────────────────────────────────────────
let isStartingStream = false;

async function startStream() {
  if (isStartingStream || streaming) return;
  isStartingStream = true;
  try {
    videoStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });

    const v = video();
    v.srcObject = videoStream;
    await v.play();

    // Wait for video to have dimensions
    await new Promise(resolve => {
      if (v.videoWidth) return resolve();
      v.onloadedmetadata = resolve;
    });

    placeholder().style.display = 'none';
    document.getElementById('btn-start-stream').classList.add('hidden');
    document.getElementById('btn-stop-stream').classList.remove('hidden');

    streaming = true;
    connectBackend();
    startSendLoop();
    startRenderLoop();
    startFpsCounter();

    showToast('Camera started', 'success');
  } catch (err) {
    showToast(`Camera error: ${err.message}`, 'error');
  } finally {
    isStartingStream = false;
  }
}


async function handleTestVideoUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (streaming) stopStream();

  const url = URL.createObjectURL(file);
  const v = video();
  v.srcObject = null;
  v.src = url;
  v.loop = true;
  await v.play();

  await new Promise(resolve => {
    if (v.videoWidth) return resolve();
    v.onloadedmetadata = resolve;
  });

  placeholder().style.display = 'none';
  document.getElementById('btn-upload-test').classList.add('hidden');
  document.getElementById('btn-stop-test-stream').classList.remove('hidden');

  streaming = true;
  connectBackend();
  startSendLoop();
  startRenderLoop();
  startFpsCounter();

  showToast('Test video loaded', 'success');
}

async function handleVideoUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (streaming) stopStream();

  const url = URL.createObjectURL(file);
  const v = video();
  v.srcObject = null;
  v.src = url;
  v.loop = true;
  await v.play();

  // Wait for video to have dimensions
  await new Promise(resolve => {
    if (v.videoWidth) return resolve();
    v.onloadedmetadata = resolve;
  });

  placeholder().style.display = 'none';
  document.getElementById('btn-start-stream').classList.add('hidden');
  document.getElementById('btn-upload-video').classList.add('hidden');
  document.getElementById('btn-stop-stream').classList.remove('hidden');

  streaming = true;
  connectBackend();
  startSendLoop();
  startRenderLoop();
  startFpsCounter();

  showToast('Test video loaded', 'success');
}

function stopStream() {
  streaming = false;

  if (sendTimer) { clearInterval(sendTimer); sendTimer = null; }
  if (fpsTimer)   { clearInterval(fpsTimer); fpsTimer = null; }
  if (rafId)      { cancelAnimationFrame(rafId); rafId = null; }

  if (videoStream) {
    videoStream.getTracks().forEach(t => t.stop());
    videoStream = null;
  }

  if (wsSocket) { wsSocket.close(); wsSocket = null; }

  // Clear overlay canvas
  const c = overlayCanvas();
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);

  const v = video();
  v.pause();
  v.srcObject = null;
  v.src = '';

  placeholder().style.display = 'flex';
  const bs = document.getElementById('btn-start-stream'); if(bs) bs.classList.remove('hidden');
  
  const bst = document.getElementById('btn-stop-stream'); if(bst) bst.classList.add('hidden');
  const bst2 = document.getElementById('btn-stop-test-stream'); if(bst2) bst2.classList.add('hidden');
  const bup = document.getElementById('btn-upload-test'); if(bup) bup.classList.remove('hidden');
  updateConnectionStatus(false);
  showToast('Stream stopped', 'info');
}

// ── WebSocket connection ──────────────────────────────────────────────────────

function connectBackend() {
  if (wsSocket && wsSocket.readyState === WebSocket.OPEN) return;

  const wsUrl = `${API.getWsUrl()}/ws/stream`;
  wsSocket = new WebSocket(wsUrl);

  wsSocket.onopen = () => {
    updateConnectionStatus(true);
    showToast('Backend connected', 'success');
  };

  wsSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'analysis') handleAnalysisResult(data);
    } catch (e) {
      console.warn('WS parse error:', e);
    }
  };

  wsSocket.onclose = () => {
    updateConnectionStatus(false);
    if (streaming) setTimeout(connectBackend, 2000);
  };

  wsSocket.onerror = () => updateConnectionStatus(false);
}

// ── Frame capture & send loop ─────────────────────────────────────────────────

function startSendLoop() {
  if (sendTimer) clearInterval(sendTimer);
  sendTimer = setInterval(captureAndSend, SEND_INTERVAL_MS);
}

function captureAndSend() {
  if (!streaming || !wsSocket || wsSocket.readyState !== WebSocket.OPEN) return;
  const v = video();
  if (!v.videoWidth) return;

  // Match hidden canvas to a max width of 640 for performance (prevents stutter/flickering)
  const MAX_WIDTH = 640;
  const scale = Math.min(1.0, MAX_WIDTH / v.videoWidth);
  const captureWidth = Math.floor(v.videoWidth * scale);
  const captureHeight = Math.floor(v.videoHeight * scale);

  if (captureCanvas.width !== captureWidth || captureCanvas.height !== captureHeight) {
    captureCanvas.width = captureWidth;
    captureCanvas.height = captureHeight;
  }

  captureCtx.drawImage(v, 0, 0, captureWidth, captureHeight);
  const b64 = captureCanvas.toDataURL('image/jpeg', 0.7).split(',')[1];
  wsSocket.send(JSON.stringify({ type: 'frame', source: currentPage === 'test-video' ? 'test' : 'live', data: b64 }));
  frameCount++;
}

// ── Smooth annotation render loop (requestAnimationFrame) ─────────────────────

function startRenderLoop() {
  if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
  
  const c = overlayCanvas();
  const ctx = c.getContext('2d');

  function render() {
    if (!streaming) return;

    const v = video();
    if (!v.videoWidth) {
      rafId = requestAnimationFrame(render);
      return;
    }

    // Match overlay canvas size to actual displayed video area (handling object-fit: contain letterboxing)
    if (typeof redrawZoneCanvas === 'function') redrawZoneCanvas();
    const rect = v.getBoundingClientRect();
    const videoRatio = v.videoWidth / v.videoHeight;
    const elementRatio = rect.width / rect.height;
    
    let renderWidth = rect.width;
    let renderHeight = rect.height;
    let offsetX = 0;
    let offsetY = 0;
    
    if (videoRatio > elementRatio) {
      renderHeight = rect.width / videoRatio;
      offsetY = (rect.height - renderHeight) / 2;
    } else {
      renderWidth = rect.height * videoRatio;
      offsetX = (rect.width - renderWidth) / 2;
    }
    
    if (c.width !== v.videoWidth || c.height !== v.videoHeight) {
      c.width = v.videoWidth;
      c.height = v.videoHeight;
    }
    
    const newWidth = `${renderWidth}px`;
    const newHeight = `${renderHeight}px`;
    const newLeft = `${offsetX}px`;
    const newTop = `${offsetY}px`;

    if (c.style.width !== newWidth) c.style.width = newWidth;
    if (c.style.height !== newHeight) c.style.height = newHeight;
    if (c.style.left !== newLeft) c.style.left = newLeft;
    if (c.style.top !== newTop) c.style.top = newTop;

    ctx.clearRect(0, 0, c.width, c.height);

    const { detections, risk, riskLabel, zones } = latestAnnotations;

    // ── Draw bounding boxes ───────────────────────────────────────────────
    for (const det of detections) {
      if (!det.bbox_normalized) continue;
      
      // Calculate pixel coordinates using normalized bbox
      const [cx, cy, bw, bh] = det.bbox_normalized;
      
      const w = bw * c.width;
      const h = bh * c.height;
      const x1 = (cx * c.width) - (w / 2);
      const y1 = (cy * c.height) - (h / 2);
      
      const color = getBboxColor(det.class);

      ctx.save();
      // Professional style bounding boxes
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(x1, y1, w, h);

      const text = `${det.class.toUpperCase()} · ${Math.round(det.confidence * 100)}%`;
      ctx.font = '600 11px "Inter", sans-serif';
      const textWidth = ctx.measureText(text).width;
      
      // Draw transparent dark pill background for text
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(x1, y1 - 22, textWidth + 12, 18);
      
      // Draw text
      ctx.fillStyle = '#ffffff';
      ctx.fillText(text, x1 + 6, y1 - 9);
      ctx.restore();
    }

    // ── Risk overlay (top-left corner) ───────────────────────────────────
    const riskColor = RISK_COLORS[risk.toLowerCase()] || '#00e676';
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.65)';
    ctx.fillRect(0, 0, 180, 34);
    ctx.font = 'bold 15px Inter, sans-serif';
    ctx.fillStyle = riskColor;
    ctx.fillText(`RISK: ${riskLabel.toUpperCase()}`, 10, 23);
    ctx.restore();

    rafId = requestAnimationFrame(render);
  }

  rafId = requestAnimationFrame(render);
}

function getBboxColor(cls) {
  const map = {
    person: '#00e676', fire: '#ff1744', knife: '#ff5252',
    gun: '#ff1744', smoke: '#ff5252',
  };
  return map[cls] || '#00d4ff';
}

// ── Handle backend analysis response ─────────────────────────────────────────

function handleAnalysisResult(data) {
  // Store annotations for render loop — DO NOT draw a JPEG frame
  latestAnnotations = {
    detections: data.detections_full || data.detections || [],
    zones:      data.zone_violations || [],
    risk:       data.risk_level || 'Low',
    riskLabel:  data.risk_level || 'Low',
    anomalies:  data.anomalies || [],
    description: data.description || '',
    action:     data.recommended_action || '',
    vlmActive:  !!data.vlm_active,
    eventStored: !!data.event_stored,
  };

  const risk = (data.risk_level || 'Low').toLowerCase();
  updateRiskBadge(risk, data.risk_level);

  // Stats
  if (data.detections) {
    sessionDetections += data.detections.length;
    if (ui('stat-detections')) ui('stat-detections').textContent = sessionDetections;
    if (ui('test-stat-detections')) ui('test-stat-detections').textContent = sessionDetections;
    renderDetections(data.detections);
  }

  if (data.vlm_active) {
    sessionVlm++;
    if (ui('stat-vlm')) ui('stat-vlm').textContent = sessionVlm;
    if (ui('test-stat-vlm')) ui('test-stat-vlm').textContent = sessionVlm;
    
    if (ui('vlm-status-tag')) {
      ui('vlm-status-tag').textContent = '✓ Active';
      ui('vlm-status-tag').style.color = 'var(--accent)';
    }
    if (ui('test-vlm-status-tag')) {
      ui('test-vlm-status-tag').textContent = '✓ Active';
      ui('test-vlm-status-tag').style.color = 'var(--accent)';
    }
  }

  if (data.description) {
    if (ui('vlm-description')) ui('vlm-description').textContent = data.description;
    if (ui('test-vlm-description')) ui('test-vlm-description').textContent = data.description;
  }
  if (data.recommended_action) {
    if (ui('vlm-action')) ui('vlm-action').textContent = '→ ' + data.recommended_action;
    if (ui('test-vlm-action')) ui('test-vlm-action').textContent = '→ ' + data.recommended_action;
  }

  renderAnomalies(data.anomalies || []);

  if (data.event_stored) {
    sessionEvents++;
    if (ui('stat-today')) ui('stat-today').textContent = sessionEvents;
    if (ui('test-stat-today')) ui('test-stat-today').textContent = sessionEvents;
    addTimelineEvent(data);
    if (risk === 'high' || risk === 'critical') {
      showAlertTicker(data.anomalies?.[0] || 'Anomaly detected', risk);
    }
    updateEventBadge(sessionEvents);
  }
}

// ── UI update helpers ─────────────────────────────────────────────────────────

function renderDetections(detections) {
  const el = ui('detection-list');
  if (!detections.length) {
    el.innerHTML = '<div style="font-size:12px;color:var(--text-muted);text-align:center;padding:12px">No detections</div>';
    return;
  }

  const grouped = {};
  for (const d of detections) grouped[d.class] = (grouped[d.class] || 0) + 1;

  el.innerHTML = Object.entries(grouped).map(([cls, count]) => {
    const conf = detections.find(d => d.class === cls)?.confidence || 0;
    const pct = Math.round(conf * 100);
    return `
      <div class="detection-item">
        <div>
          <div style="font-weight:500;color:var(--text-primary)">${cls} <span style="color:var(--text-muted)">×${count}</span></div>
          <div class="conf-bar" style="width:${pct}%"></div>
        </div>
        <span class="tag">${pct}%</span>
      </div>`;
  }).join('');
}

function renderAnomalies(anomalies) {
  const el = document.getElementById('anomaly-list');
  document.getElementById('anomaly-count').textContent = anomalies.length;
  if (!anomalies.length) {
    el.innerHTML = `<div class="empty-state" style="padding:16px"><div class="icon" style="font-size:20px">✅</div><p>No anomalies detected</p></div>`;
    return;
  }
  el.innerHTML = anomalies.map(a => `
    <div class="timeline-item high" style="font-size:12px;margin-bottom:4px">
      <span>⚠️</span><span>${a}</span>
    </div>`).join('');
}

function addTimelineEvent(data) {
  const el = ui('live-timeline');
  const risk = (data.risk_level || 'Low').toLowerCase();
  const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const placeholder = el.querySelector('[style*="text-align:center"]');
  if (placeholder) placeholder.remove();

  const item = document.createElement('div');
  item.className = `timeline-item ${risk}`;
  item.innerHTML = `
    <div style="color:var(--text-muted);white-space:nowrap">${time}</div>
    <div style="flex:1">
      <div style="font-weight:600;color:var(--text-primary)">${data.anomalies?.[0] || 'Event'}</div>
      <div style="color:var(--text-muted)">${(data.description || '').substring(0, 80)}${(data.description?.length || 0) > 80 ? '...' : ''}</div>
    </div>`;
  el.insertBefore(item, el.firstChild);
  while (el.children.length > 10) el.removeChild(el.lastChild);
}

function showAlertTicker(text, risk) {
  const ticker = ui('alert-ticker');
  if (ticker) {
    ui('alert-ticker-text').textContent = text;
    ticker.classList.add('visible');
    if (risk === 'high' || risk === 'critical') setTimeout(() => ticker.classList.remove('visible'), 8000);
  }
  const testTicker = ui('test-alert-ticker');
  if (testTicker) {
    ui('test-alert-ticker-text').textContent = text;
    testTicker.classList.add('visible');
    if (risk === 'high' || risk === 'critical') setTimeout(() => testTicker.classList.remove('visible'), 8000);
  }
}

function startFpsCounter() {
  let lastCount = 0;
  fpsTimer = setInterval(() => {
    ui('fps-counter').textContent = `${frameCount - lastCount} fps`;
    lastCount = frameCount;
  }, 1000);
}

function updateConnectionStatus(connected) {
  document.getElementById('conn-dot').className = 'status-dot ' + (connected ? '' : 'offline');
  document.getElementById('conn-status').textContent = connected ? 'Connected' : 'Disconnected';
}

function updateRiskBadge(riskLower, riskLabel) {
  const badge = document.getElementById('global-risk-badge');
  if (badge) {
    badge.className = `risk-badge ${riskLower}`;
    document.getElementById('global-risk-text').textContent = (riskLabel || 'Low').toUpperCase();
  }
  const el = ui('stat-risk');
  const testEl = ui('test-stat-risk');
  const colors = { low:'var(--risk-low)', medium:'var(--risk-medium)', high:'var(--risk-high)', critical:'var(--risk-critical)' };
  const color = colors[riskLower] || 'var(--risk-low)';
  
  if (el) {
    el.textContent = (riskLabel || 'Low').toUpperCase();
    el.style.color = color;
  }
  if (testEl) {
    testEl.textContent = (riskLabel || 'Low').toUpperCase();
    testEl.style.color = color;
  }
}

function updateEventBadge(count) {
  const badge = document.getElementById('badge-events');
  badge.textContent = count;
  badge.classList.toggle('visible', count > 0);
}
