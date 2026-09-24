/**
 * js/zone_canvas.js — Interactive polygon zone drawing tool.
 */

let zoneCanvas = null;
let zoneCtx = null;
let currentPoints = [];
let currentZoneType = 'restricted';
let zoneImage = null;
let currentSource = 'live'; // 'live' or 'test'

const ZONE_COLORS = {
  restricted: { fill: 'rgba(255,82,82,0.2)', stroke: '#ff5252', label: '#ff5252' },
  safe: { fill: 'rgba(0,230,118,0.2)', stroke: '#00e676', label: '#00e676' },
};

function initZoneCanvas(source = 'live') {
  currentSource = source;
  const canvasId = source === 'test' ? 'test-zone-canvas' : (source === 'live' ? 'live-zone-canvas' : 'zone-canvas');
  zoneCanvas = document.getElementById(canvasId);
  if (!zoneCanvas) return;
  zoneCtx = zoneCanvas.getContext('2d');

  zoneCanvas.onclick = onCanvasClick;
  zoneCanvas.ondblclick = onCanvasDoubleClick;
  zoneCanvas.onmousemove = onCanvasMouseMove;

  loadZoneBackground();
  loadZoneList();
}

function captureZoneSnapshot(source) {
  const videoId = source === 'test-video' ? 'test-video-source' : 'video-source';
  const video = document.getElementById(videoId);
  
  if (video && video.videoWidth > 0) {
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = video.videoWidth;
    tempCanvas.height = video.videoHeight;
    const ctx = tempCanvas.getContext('2d');
    ctx.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);
    
    const img = new Image();
    img.src = tempCanvas.toDataURL('image/jpeg', 0.9);
    img.onload = () => {
      zoneImage = img;
      redrawZoneCanvas();
    };
  }
}

function loadZoneBackground() {
  if (!zoneCanvas || !zoneCtx) return;
  
  // If we already have a snapshot, just redraw
  if (zoneImage) {
    redrawZoneCanvas();
    return;
  }
  
  // Otherwise, try to capture from video
  captureZoneSnapshot(currentSource === 'test' ? 'test-video' : 'live');
  
  if (!zoneImage) {
    // Draw placeholder
    zoneCtx.fillStyle = currentSource === 'test' ? 'transparent' : '#0d1117';
    zoneCtx.fillRect(0, 0, zoneCanvas.width, zoneCanvas.height);
    if (currentSource !== 'test') {
      zoneCtx.fillStyle = 'rgba(255,255,255,0.1)';
      zoneCtx.font = '14px Inter';
      zoneCtx.textAlign = 'center';
      zoneCtx.fillText('Start camera stream first to see live feed', zoneCanvas.width / 2, zoneCanvas.height / 2 - 10);
      zoneCtx.fillText('Then define zones here', zoneCanvas.width / 2, zoneCanvas.height / 2 + 14);
    }
  }
}

let hoverPoint = null;

function onCanvasMouseMove(e) {
  hoverPoint = getCanvasPoint(e);
  redrawZoneCanvas();
}

function onCanvasClick(e) {
  const pt = getCanvasPoint(e);
  currentPoints.push(pt);
  redrawZoneCanvas();
}

function onCanvasDoubleClick(e) {
  currentPoints.pop();
  if (currentPoints.length < 3) {
    showToast('Zone needs at least 3 points', 'warning');
    return;
  }
  saveCurrentZone();
}

function getCanvasPoint(e) {
  const rect = zoneCanvas.getBoundingClientRect();
  const scaleX = zoneCanvas.width / rect.width;
  const scaleY = zoneCanvas.height / rect.height;
  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY,
    nx: ((e.clientX - rect.left) * scaleX) / zoneCanvas.width,
    ny: ((e.clientY - rect.top) * scaleY) / zoneCanvas.height,
  };
}

function redrawZoneCanvas() {
  if (!zoneCanvas || !zoneCtx) return;
  const ctx = zoneCtx;
  const w = zoneCanvas.width;
  const h = zoneCanvas.height;

  ctx.clearRect(0, 0, w, h);
  
  const videoId = currentSource === 'test' ? 'test-video-source' : 'video-source';
  const video = document.getElementById(videoId);
  
  if (video && video.videoWidth > 0 && !video.paused) {
    const videoRatio = video.videoWidth / video.videoHeight;
    const canRatio = w / h;
    let dx = 0, dy = 0, dw = w, dh = h;
    
    if (videoRatio > canRatio) {
      dh = w / videoRatio;
      dy = (h - dh) / 2;
    } else {
      dw = h * videoRatio;
      dx = (w - dw) / 2;
    }
    // Only draw video background if it's the Settings page canvas.
    // For test video and live video, the canvas is an OVERLAY, so don't draw the video into it!
    if (currentSource === 'settings') {
      ctx.drawImage(video, dx, dy, dw, dh);
    }
  } else if (zoneImage && currentSource === 'settings') {
    ctx.drawImage(zoneImage, 0, 0, w, h);
  } else if (currentSource === 'settings') {
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);
  }

  // Draw current in-progress polygon
  if (currentPoints.length > 0) {
    const col = ZONE_COLORS[currentZoneType];
    ctx.save();
    ctx.strokeStyle = col.stroke;
    ctx.fillStyle = col.fill;
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 4]);

    ctx.beginPath();
    ctx.moveTo(currentPoints[0].x, currentPoints[0].y);
    for (let i = 1; i < currentPoints.length; i++) {
      ctx.lineTo(currentPoints[i].x, currentPoints[i].y);
    }
    if (hoverPoint) ctx.lineTo(hoverPoint.x, hoverPoint.y);
    ctx.stroke();
    ctx.fill();
    ctx.setLineDash([]);
    ctx.restore();

    for (const pt of currentPoints) {
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
      ctx.fillStyle = col.stroke;
      ctx.fill();
    }

    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(4, 4, 280, 24);
    ctx.fillStyle = '#ffffff';
    ctx.font = '12px Inter';
    ctx.textAlign = 'left';
    ctx.fillText(`${currentPoints.length} points — double-click to finish zone`, 10, 20);
  }
}

async function saveCurrentZone() {
  const nameinput = document.getElementById(currentSource === 'test' ? 'test-zone-name' : (currentSource === 'live' ? 'live-zone-name' : 'zone-name-input'));
  const name = nameinput.value.trim() || `${currentZoneType === 'restricted' ? 'Restricted' : 'Safe'} Zone ${Date.now().toString().slice(-4)}`;

  const normalizedPoints = currentPoints.map(p => [p.nx, p.ny]);

  try {
    await API.createZone({
      name,
      zone_type: currentZoneType,
      source: currentSource,
      points: normalizedPoints,
      color: currentZoneType === 'restricted' ? '#FF3333' : '#33FF88',
    });

    showToast(`Zone "${name}" saved!`, 'success');
    nameinput.value = '';
    currentPoints = [];
    hoverPoint = null;
    redrawZoneCanvas();
    loadZoneList();
  } catch (err) {
    showToast(`Failed to save zone: ${err.message}`, 'error');
  }
}

function setZoneType(type, el) {
  currentZoneType = type;
  document.querySelectorAll('.zone-type-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
}

function setTestZoneType(type, el) {
  currentZoneType = type;
  document.querySelectorAll('#page-test-video .zone-type-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
}

function setLiveZoneType(type, el) {
  currentZoneType = type;
  document.querySelectorAll('#page-live .zone-type-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
}

function clearZoneDrawing() {
  currentPoints = [];
  hoverPoint = null;
  redrawZoneCanvas();
}
window.clearTestZone = clearZoneDrawing; // For test canvas
window.clearLiveZone = clearZoneDrawing; // For live canvas

async function loadZoneList() {
  try {
    const data = await API.getZones(currentSource);
    renderZoneList(data.zones || []);
  } catch (e) {
    console.warn('Could not load zones:', e);
  }
}

function renderZoneList(zones) {
  // Only the Settings page has a zone-list to render to currently
  const el = document.getElementById('zone-list');
  if (!el || currentSource === 'test') return; // Do not render list in test video for now unless added
  if (!zones.length) {
    el.innerHTML = '<div style="font-size:12px;color:var(--text-muted)">No zones configured. Click on the canvas above to draw zones.</div>';
    return;
  }

  el.innerHTML = zones.map(z => `
    <div class="zone-item">
      <div class="zone-color-dot" style="background:${z.color}"></div>
      <div style="flex:1">
        <div style="font-weight:600">${z.name}</div>
        <div class="text-xs text-muted">${z.zone_type.toUpperCase()} · ${z.points.length} points</div>
      </div>
      <button class="btn btn-ghost btn-sm" onclick="deleteZone('${z.zone_id}')">🗑</button>
    </div>`).join('');
}

async function deleteZone(id) {
  try {
    await API.deleteZone(id);
    showToast('Zone deleted', 'info');
    loadZoneList();
  } catch (err) {
    showToast(`Delete failed: ${err.message}`, 'error');
  }
}
