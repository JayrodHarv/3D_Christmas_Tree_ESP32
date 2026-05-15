// ── Effect list — keep in sync with Effect enum in effects.h ──────────────────
const EFFECTS = [
  { id: 0, name: 'Spiral'   },
  { id: 1, name: 'Rainbow'  },
  { id: 2, name: 'Spectrum' },
  { id: 3, name: 'Twinkle'  },
  { id: 4, name: 'Wave'     },
  { id: 5, name: 'Solid'    },
];

// ── State ─────────────────────────────────────────────────────────────────────
let NUM_LEDS = 0;
let brightnessTimer  = null;
let pollInterval     = null;
let countdownInterval = null;
let schedulerEndTime = null;

// ── Boot ──────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  buildEffectButtons();
  wrapCardsInLayout();
  startPolling();
});

// ── Wrap cards in layout div for CSS grid ─────────────────────────────────────
function wrapCardsInLayout() {
  const cards = [...document.querySelectorAll('.card')];
  const layout = document.createElement('div');
  layout.className = 'layout';
  cards[0].parentNode.insertBefore(layout, cards[0]);
  cards.forEach(c => layout.appendChild(c));
}

// ── Build effect buttons dynamically from EFFECTS list ────────────────────────
function buildEffectButtons() {
  const grid = document.getElementById('effect-buttons');
  EFFECTS.forEach(fx => {
    const btn = document.createElement('button');
    btn.id        = `fx-btn-${fx.id}`;
    btn.textContent = fx.name;
    btn.onclick   = () => setEffect(fx.id);
    grid.appendChild(btn);
  });
}

// ── Polling — fetch status every 2 seconds ────────────────────────────────────
function startPolling() {
  fetchStatus();
  pollInterval = setInterval(fetchStatus, 2000);
}

async function fetchStatus() {
  try {
    const res  = await fetch('/status');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    updateUI(data);
  } catch (e) {
    log('Status fetch failed: ' + e.message, 'err');
  }
}

function updateUI(data) {
  NUM_LEDS = data.num_leds;

  // Status card
  const effectName = EFFECTS[data.current_effect]?.name ?? '—';
  setText('s-effect',     effectName);
  setText('s-brightness', data.brightness);
  setText('s-scheduler',  data.scheduler_running ? '▶ Running' : '⏹ Off');
  setText('s-coords',     data.coords_loaded
                            ? `${data.coord_count} LEDs loaded`
                            : 'Not loaded');

  // Brightness slider (don't update while user is dragging)
  const slider = document.getElementById('brightness-slider');
  if (!slider.matches(':active')) {
    slider.value = data.brightness;
    setText('brightness-val', data.brightness);
  }

  // Effect buttons — highlight active
  EFFECTS.forEach(fx => {
    const btn = document.getElementById(`fx-btn-${fx.id}`);
    if (btn) btn.classList.toggle('active', fx.id === data.current_effect);
  });

  // Scheduler button label
  const schedBtn = document.getElementById('btn-scheduler');
  if (data.scheduler_running) {
    schedBtn.textContent = '⏹ Stop Scheduler';
    schedBtn.classList.add('active');
    // Start local countdown from remaining ms
    if (data.time_remaining_ms !== undefined) {
      schedulerEndTime = Date.now() + data.time_remaining_ms;
      startCountdown();
    }
  } else {
    schedBtn.textContent = '▶ Start Scheduler';
    schedBtn.classList.remove('active');
    stopCountdown();
    setText('s-countdown', '—');
  }
}

// ── Countdown timer (runs locally between polls) ──────────────────────────────
function startCountdown() {
  stopCountdown();
  countdownInterval = setInterval(() => {
    const remaining = schedulerEndTime - Date.now();
    if (remaining <= 0) {
      setText('s-countdown', '—');
      stopCountdown();
    } else {
      setText('s-countdown', `${Math.ceil(remaining / 1000)}s`);
    }
  }, 500);
}

function stopCountdown() {
  if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
}

// ── Commands ──────────────────────────────────────────────────────────────────
async function cmd(action) {
  try {
    const res = await fetch(`/cmd?action=${action}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    log(`→ ${action}`, 'ok');
    fetchStatus();
  } catch (e) {
    log(`cmd '${action}' failed: ${e.message}`, 'err');
  }
}

async function setEffect(id) {
  try {
    const res = await fetch(`/cmd?action=effect&id=${id}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    log(`→ effect ${EFFECTS[id]?.name}`, 'ok');
    fetchStatus();
  } catch (e) {
    log(`setEffect failed: ${e.message}`, 'err');
  }
}

// ── Brightness slider ─────────────────────────────────────────────────────────
function onBrightnessSlide(val) {
  // Update label instantly while dragging
  setText('brightness-val', val);
  // Debounce the actual HTTP request
  clearTimeout(brightnessTimer);
  brightnessTimer = setTimeout(() => sendBrightness(val), 80);
}

function onBrightnessCommit(val) {
  clearTimeout(brightnessTimer);
  sendBrightness(val);
}

async function sendBrightness(val) {
  try {
    const res = await fetch(`/cmd?action=brightness&value=${val}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    log(`→ brightness ${val}`, 'ok');
  } catch (e) {
    log(`brightness failed: ${e.message}`, 'err');
  }
}

// ── Coordinate upload ─────────────────────────────────────────────────────────
async function uploadCoords() {
  const file      = document.getElementById('fileInput').files[0];
  const statusEl  = document.getElementById('upload-status');

  if (!file) {
    setUploadStatus('Select a file first', false);
    return;
  }

  setUploadStatus('Uploading...', true);
  const form = new FormData();
  form.append('file', file, 'coords.json');

  try {
    const res = await fetch('/upload', { method: 'POST', body: form });
    const msg = await res.text();
    setUploadStatus(res.ok ? '✓ ' + msg : '✗ ' + msg, res.ok);
    log('Coords uploaded', res.ok ? 'ok' : 'err');
    if (res.ok) fetchStatus();
  } catch (e) {
    setUploadStatus('Upload failed: ' + e.message, false);
  }
}

function setUploadStatus(msg, ok) {
  const el = document.getElementById('upload-status');
  el.textContent = msg;
  el.className   = ok ? 'ok' : 'err';
}

// ── Scan ──────────────────────────────────────────────────────────────────────
let scanPaused   = false;
let scanInterval = null;

async function scanCmd(action) {
  try {
    await fetch(`/scan/cmd?action=${action}`);
    fetchScanStatus();
    if (action === 'stop') stopScanPolling();
    if (action === 'start') startScanPolling();
  } catch(e) {
    log('Scan cmd failed: ' + e, 'err');
  }
}

async function scanGoto() {
  const idx = prompt('Go to LED index (0 - ' + (NUM_LEDS - 1) + '):');
  if (idx === null || idx === '') return;
  await fetch(`/scan/cmd?action=goto&index=${parseInt(idx)}`);
  fetchScanStatus();
}

async function togglePause() {
  scanPaused = !scanPaused;
  await fetch(`/scan/cmd?action=${scanPaused ? 'pause' : 'resume'}`);
  document.getElementById('btn-pause').textContent = scanPaused ? '▶ Resume' : '⏸ Pause';
}

function startScanPolling() {
  stopScanPolling();
  fetchScanStatus();
  scanInterval = setInterval(fetchScanStatus, 500);
}

function stopScanPolling() {
  if (scanInterval) { clearInterval(scanInterval); scanInterval = null; }
}

async function fetchScanStatus() {
  try {
    const res  = await fetch('/scan/status');
    const data = await res.json();
    updateScanUI(data);
  } catch(e) {}
}

function updateScanUI(data) {
  const idle   = document.getElementById('scan-idle');
  const active = document.getElementById('scan-active');
  const running = data.state !== 0;   // 0 = SCAN_IDLE

  idle.style.display   = running ? 'none'  : 'block';
  active.style.display = running ? 'block' : 'none';

  if (running) {
    setText('scan-current', data.current);
    setText('scan-total',   data.total);
    const pct = ((data.current + 1) / data.total * 100).toFixed(1);
    document.getElementById('progress-fill').style.width = pct + '%';
  }
}

// ── Log ───────────────────────────────────────────────────────────────────────
function log(msg, type = '') {
  const container = document.getElementById('log');
  const entry     = document.createElement('div');
  const time      = new Date().toLocaleTimeString();
  entry.className = `log-entry ${type}`;
  entry.textContent = `[${time}] ${msg}`;
  container.prepend(entry);
  // Keep log from growing forever
  while (container.children.length > 100) {
    container.removeChild(container.lastChild);
  }
}

function clearLog() {
  document.getElementById('log').innerHTML = '';
}

// ── Utility ───────────────────────────────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}