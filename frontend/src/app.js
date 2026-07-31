import './styles.css';
import { renderSidebar } from './components/sidebar.js';
import { renderWorkspace } from './components/workspace.js';
import { updateHistory } from './components/history.js';
import { executeForensicAnalysis, executeBatchAnalysis, fetchHistory } from './utils/api.js';
import { compilePdfReport } from './utils/report.js';

// HTML Shell Injection
// Mounts the primary layout components (Sidebar and Workspace) into the root div
document.getElementById('app').innerHTML = `
  <div class="layout">
    ${renderSidebar()}
    ${renderWorkspace()}
  </div>
`;

// DOM Element References
// Core UI triggers and display containers
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const analyzeBtn = document.getElementById('analyze-btn');
const previewWrapper = document.getElementById('preview-wrapper');

// Media viewers for source and heatmap overlays
const previewImg = document.getElementById('preview-img');
const videoPreview = document.getElementById('video-preview');
const heatmapImg = document.getElementById('heatmap-img');
const heatmapPlaceholder = document.getElementById('heatmap-placeholder');

// Overlay layers for the attention rollout map
const overlayBaseImg = document.getElementById('overlay-base-img');
const overlayBaseVideo = document.getElementById('overlay-base-video');
const overlayHeat = document.getElementById('overlay-heat');

// State views and dynamic data containers
const idleState = document.getElementById('idle-state');
const resultState = document.getElementById('result-state');
const batchState = document.getElementById('batch-state');
const batchSummary = document.getElementById('batch-summary');
const batchList = document.getElementById('batch-list');
const gaugeFill = document.getElementById('gauge-fill');
const historyList = document.getElementById('history-list');

// Application State Variables
let selectedFile = null;
let isBatchMode = false;
let selectedBatchFiles = [];
let currentReport = null;
let sessionHistory = [];
let loadingInterval = null;
let objectUrlCache = null;

// History Filter State
let activeFilter = 'ALL';
let searchQuery = '';

// Database Synchronization
// Hydrates the session history from the backend audit ledger on initial page load.
// Relative /api paths work in both dev (proxied by vite.config.js) and prod
// (same origin, served by FastAPI) — no separate base URL needed.
async function syncDatabaseHistory() {
  try {
    const data = await fetchHistory();
    sessionHistory = data.entries.reverse();
    applyHistoryFilters();
  } catch (err) {
    console.error("Database sync failed:", err);
  }
}
syncDatabaseHistory();

function handleThrottled() {
  document.getElementById('warn-sys-text').textContent =
    'Rate limit exceeded — please wait a moment before retrying.';
  document.getElementById('warn-sys-error').classList.add('visible');
  previewWrapper.classList.remove('scanning');
}

// Filter Engine
// Re-evaluates the history array based on the active verdict chip and search query
function applyHistoryFilters() {
  let filtered = sessionHistory;
  
  if (activeFilter !== 'ALL') {
      filtered = filtered.filter(item => item.verdict === activeFilter);
  }
  
  if (searchQuery.trim() !== '') {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(item => item.filename.toLowerCase().includes(q));
  }
  
  updateHistory(filtered, sessionHistory);
}

// Search and Filter Event Listeners
document.getElementById('history-search').addEventListener('input', (e) => {
    searchQuery = e.target.value;
    applyHistoryFilters();
});

document.querySelectorAll('.filter-chip').forEach(btn => {
    btn.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        activeFilter = e.target.dataset.filter;
        applyHistoryFilters();
    });
});

// File Ingestion Listeners
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => handleFiles(e.target.files));

// Drag and drop UX handling
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', e => { e.preventDefault(); dropZone.classList.remove('dragover'); });
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  handleFiles(e.dataTransfer.files);
});

// Routes to the existing single-file flow, or batch mode when more than
// one file is selected/dropped.
function handleFiles(fileList) {
  const files = Array.from(fileList || []);
  if (files.length === 0) return;

  if (files.length === 1) {
    isBatchMode = false;
    selectedBatchFiles = [];
    handleFile(files[0]);
    return;
  }

  isBatchMode = true;
  selectedBatchFiles = files;
  selectedFile = null;

  batchState.classList.remove('visible');
  resultState.classList.remove('visible');
  idleState.style.display = 'flex';
  document.querySelectorAll('.hist-item').forEach(el => el.classList.remove('active-log'));

  analyzeBtn.disabled = false;
  analyzeBtn.textContent = `ANALYZE BATCH (${files.length} FILES)`;
}

// Workspace Tab Navigation (Source / Heatmap / Overlay)
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-layer').forEach(l => l.classList.remove('active'));
    
    const targetId = e.target.dataset.target;
    e.target.classList.add('active');
    document.getElementById(targetId).classList.add('active');
  });
});

// Session History Selection
// Allows analysts to click an old log and restore that exact state to the dashboard
historyList.addEventListener('click', (e) => {
  const item = e.target.closest('.hist-item');
  if (!item) return;

  const hash = item.dataset.hash;
  const entry = sessionHistory.find(x => x.file_sha256 === hash);
  
  if (entry) {
    document.querySelectorAll('.hist-item').forEach(el => el.classList.remove('active-log'));
    item.classList.add('active-log');

    // Free memory from the currently active file before loading historical data
    if (objectUrlCache) {
      URL.revokeObjectURL(objectUrlCache);
      objectUrlCache = null;
    }
    
    idleState.style.display = 'none';
    resultState.classList.add('visible');
    previewImg.style.display = 'none';
    videoPreview.style.display = 'none';
    overlayBaseImg.style.display = 'none';
    overlayBaseVideo.style.display = 'none';
    
    renderResult(entry, entry.filename);
  }
});

// File Processing Initialization
// Handles local object URLs and configures the media view before API transmission
function handleFile(file) {
  if (!file) return;
  selectedFile = file;
  analyzeBtn.disabled = false;
  analyzeBtn.textContent = `ANALYZE: ${file.name.length > 20 ? file.name.slice(0,18)+'…' : file.name}`;
  
  if (objectUrlCache) URL.revokeObjectURL(objectUrlCache);
  objectUrlCache = URL.createObjectURL(file);
  
  const isVid = file.type.startsWith('video/');
  
  [previewImg, videoPreview, overlayBaseImg, overlayBaseVideo].forEach(el => el.style.display = 'none');

  if (isVid) { 
    videoPreview.src = objectUrlCache; 
    videoPreview.style.display = 'block'; 
    overlayBaseVideo.src = objectUrlCache;
    overlayBaseVideo.style.display = 'block';
  } else { 
    previewImg.src = objectUrlCache; 
    previewImg.style.display = 'block'; 
    overlayBaseImg.src = objectUrlCache;
    overlayBaseImg.style.display = 'block';
  }
  
  heatmapImg.style.display = 'none';
  overlayHeat.style.display = 'none';
  heatmapPlaceholder.style.display = 'block';
  
  idleState.style.display = 'flex';
  resultState.classList.remove('visible');
  batchState.classList.remove('visible');
  gaugeFill.style.strokeDashoffset = 326.7;
  
  document.querySelectorAll('.hist-item').forEach(el => el.classList.remove('active-log'));
  document.getElementById('stat-score-sub').textContent = 'Pending';
  document.getElementById('stat-face-sub').textContent = 'Pending';
  document.getElementById('stat-qual-sub').textContent = 'Pending';
}

// UI Loading State Manager
function setLoading(on) {
  analyzeBtn.disabled = on;
  if (!on) {
    clearInterval(loadingInterval);
    analyzeBtn.textContent = `ANALYZE: ${selectedFile.name.length > 20 ? selectedFile.name.slice(0,18)+'…' : selectedFile.name}`;
    return;
  }
  
  const steps = ['Extracting Frames...', 'Running MTCNN...', 'Attention Rollout...', 'Aggregating Scores...'];
  let i = 0;
  analyzeBtn.textContent = steps[0];
  loadingInterval = setInterval(() => {
    i = (i + 1) % steps.length;
    analyzeBtn.textContent = steps[i];
  }, 400);
}

// Core Execution Pipeline
analyzeBtn.addEventListener('click', () => {
  if (isBatchMode) {
    runBatchAnalysis();
  } else {
    runSingleAnalysis();
  }
});

async function runSingleAnalysis() {
  idleState.style.display = 'none';
  resultState.classList.add('visible');
  batchState.classList.remove('visible');
  previewWrapper.classList.add('scanning');

  document.querySelector('[data-target="tab-source"]').click();

  setLoading(true);
  gaugeFill.style.strokeDashoffset = 326.7;
  document.getElementById('low-conf-warning').style.display = 'none';
  document.getElementById('low-qual-warning').style.display = 'none';
  document.getElementById('disposition-banner').classList.remove('visible');
  document.getElementById('face-list').style.display = 'none';
  document.getElementById('warn-sys-error').classList.remove('visible');

  const explain = document.getElementById('explain-toggle').checked;

  try {
    const data = await executeForensicAnalysis(selectedFile, explain, handleThrottled);
    if (!data) return; // request was rate-limited; handleThrottled already surfaced it

    previewWrapper.classList.remove('scanning');
    renderResult(data, selectedFile.name);

    sessionHistory.unshift({ timestamp: new Date().toISOString(), filename: selectedFile.name, ...data });
    applyHistoryFilters();

    // Automatically highlight the newest log entry
    setTimeout(() => {
        const firstLog = document.querySelector('.hist-item');
        if(firstLog) firstLog.classList.add('active-log');
    }, 100);

  } catch (err) {
    document.getElementById('warn-sys-text').textContent = err.message;
    document.getElementById('warn-sys-error').classList.add('visible');
    previewWrapper.classList.remove('scanning');
  } finally {
    setLoading(false);
  }
}

// Batch Execution Pipeline
async function runBatchAnalysis() {
  idleState.style.display = 'none';
  resultState.classList.remove('visible');
  batchState.classList.add('visible');
  document.getElementById('warn-sys-error').classList.remove('visible');

  analyzeBtn.disabled = true;
  const fileCount = selectedBatchFiles.length;
  analyzeBtn.textContent = `Analyzing ${fileCount} files...`;

  try {
    const data = await executeBatchAnalysis(selectedBatchFiles, handleThrottled);
    if (!data) return; // rate-limited; handleThrottled already surfaced it

    renderBatchResult(data);

    const timestamp = new Date().toISOString();
    data.results.forEach(r => {
      if (!r.error) sessionHistory.unshift({ timestamp, ...r });
    });
    applyHistoryFilters();
  } catch (err) {
    document.getElementById('warn-sys-text').textContent = err.message;
    document.getElementById('warn-sys-error').classList.add('visible');
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = `ANALYZE BATCH (${fileCount} FILES)`;
  }
}

function renderBatchResult(data) {
  const { summary, results } = data;

  batchSummary.innerHTML = `
    <span class="batch-stat">TOTAL<strong>${summary.total}</strong></span>
    <span class="batch-stat batch-real">REAL<strong>${summary.real}</strong></span>
    <span class="batch-stat batch-fake">FAKE<strong>${summary.fake}</strong></span>
    <span class="batch-stat batch-error">ERRORS<strong>${summary.errors}</strong></span>
  `;

  batchList.innerHTML = results.map(r => {
    if (r.error) {
      return `<div class="batch-row batch-row-error">
        <span class="batch-row-name" title="${r.filename}">${r.filename}</span>
        <span class="batch-row-badge error">ERROR</span>
        <span class="batch-row-detail" title="${r.error}">${r.error}</span>
      </div>`;
    }
    const cls = r.verdict === 'FAKE' ? 'fake' : 'real';
    const multi = r.multiple_faces_detected ? ' &middot; multi-face' : '';
    return `<div class="batch-row">
      <span class="batch-row-name" title="${r.filename}">${r.filename}</span>
      <span class="batch-row-badge ${cls}">${r.verdict}</span>
      <span class="batch-row-detail">${r.confidence}% &middot; ${r.face_quality}${multi}</span>
    </div>`;
  }).join('');
}

// UI Result Renderer
// Translates the backend data dictionary into the visual DOM elements
function renderResult(data, filename) {
  currentReport = { ...data, filename };
  const isFake = data.verdict === 'FAKE';
  const cls = isFake ? 'fake' : 'real';

  document.getElementById('trust-title').textContent = data.verdict;
  document.getElementById('trust-title').className = `trust-title title-${cls}`;
  document.getElementById('gauge-conf').textContent = `${data.confidence}%`;
  
  gaugeFill.className.baseVal = `gauge-fill ${cls}`;
  setTimeout(() => { gaugeFill.style.strokeDashoffset = 326.7 - (326.7 * (data.confidence / 100)); }, 100);

  document.getElementById('stat-score').textContent = data.probability.toFixed(4);
  document.getElementById('stat-score').style.color = isFake ? 'var(--red)' : 'var(--green)';
  document.getElementById('stat-score-sub').textContent = `${(data.probability * 100).toFixed(1)}% fake probability`;
  
  document.getElementById('stat-face').textContent = data.face_detected ? 'MTCNN Extract' : 'None';
  document.getElementById('stat-face-sub').textContent = data.face_detected ? 'Subject Detected' : 'No face found';
  
  document.getElementById('stat-quality').textContent = data.face_quality;
  document.getElementById('stat-qual-sub').textContent = data.face_quality === 'N/A' ? 'Not evaluated' : 'Frame-level evaluation';
  
  document.getElementById('kpi-format').textContent = data.type.toUpperCase();
  document.getElementById('kpi-frames').textContent = data.frames_analyzed;
  document.getElementById('kpi-time').textContent = `${data.processing_time_sec}s`;
  
  if (data.is_low_confidence) document.getElementById('low-conf-warning').style.display = 'flex';
  if (data.face_quality === "Poor") document.getElementById('low-qual-warning').style.display = 'flex';

  if (data.disposition) {
    document.getElementById('disposition-text').textContent = data.disposition;
    document.getElementById('disposition-banner').classList.add('visible');
  }

  // Independent per-face verdicts (multiple faces in a single image only —
  // see the disposition note above for the video-with-multiple-faces case)
  const faceList = document.getElementById('face-list');
  if (data.faces && data.faces.length > 0) {
    document.getElementById('face-list-rows').innerHTML = data.faces.map((f, idx) => {
      const fcls = f.verdict === 'FAKE' ? 'fake' : 'real';
      return `<div class="batch-row">
        <span class="batch-row-name">Face ${idx + 1}${idx === 0 ? ' (primary)' : ''}</span>
        <span class="batch-row-badge ${fcls}">${f.verdict}</span>
        <span class="batch-row-detail">${f.confidence}% &middot; ${f.face_quality}</span>
      </div>`;
    }).join('');
    faceList.style.display = 'flex';
  } else {
    faceList.style.display = 'none';
  }

  // Inject Base64 heatmap data if the Attention Rollout was requested
  if (data.explainability_maps && data.explainability_maps.length > 0) {
      const b64 = `data:image/jpeg;base64,${data.explainability_maps[0]}`;
      heatmapImg.src = b64;
      overlayHeat.src = b64;
      heatmapImg.style.display = 'block';
      overlayHeat.style.display = 'block';
      heatmapPlaceholder.style.display = 'none';
  } else {
      heatmapImg.style.display = 'none';
      overlayHeat.style.display = 'none';
      heatmapPlaceholder.style.display = 'block';
  }
}

// Session Cleardown
document.getElementById('clear-history-btn').addEventListener('click', () => {
  if (sessionHistory.length === 0) return;
  if (confirm("Clear the current session history view? (Note: Database logs remain securely stored in the backend)")) {
    sessionHistory = [];
    applyHistoryFilters();
    idleState.style.display = 'flex';
    resultState.classList.remove('visible');
    batchState.classList.remove('visible');
    selectedFile = null;
    isBatchMode = false;
    selectedBatchFiles = [];
    analyzeBtn.textContent = 'AWAITING EVIDENCE';
    analyzeBtn.disabled = true;
    gaugeFill.style.strokeDashoffset = 326.7;
  }
});

// PDF Report Generation (jsPDF, via utils/report.js)
document.getElementById('export-btn').addEventListener('click', () => {
  if (!currentReport) return;
  compilePdfReport(currentReport);
});
