import './styles.css';
import { renderSidebar } from './components/sidebar.js';
import { renderWorkspace } from './components/workspace.js';
import { updateHistory } from './components/history.js';

// 1. INJECT CUSTOM HTML SHELL
document.getElementById('app').innerHTML = `
  <div class="layout">
    ${renderSidebar()}
    ${renderWorkspace()}
  </div>
`;

// 2. DOM QUERIES
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const analyzeBtn = document.getElementById('analyze-btn');
const previewWrapper = document.getElementById('preview-wrapper');

const previewImg = document.getElementById('preview-img');
const videoPreview = document.getElementById('video-preview');
const heatmapImg = document.getElementById('heatmap-img');
const heatmapPlaceholder = document.getElementById('heatmap-placeholder');

const overlayBaseImg = document.getElementById('overlay-base-img');
const overlayBaseVideo = document.getElementById('overlay-base-video');
const overlayHeat = document.getElementById('overlay-heat');

const idleState = document.getElementById('idle-state');
const resultState = document.getElementById('result-state');
const gaugeFill = document.getElementById('gauge-fill');
const historyList = document.getElementById('history-list');

// 3. STATE & INIT
let selectedFile = null;
let currentReport = null;
let sessionHistory = [];
let loadingInterval = null;
let objectUrlCache = null; 

// PHASE 3: Filter State
let activeFilter = 'ALL';
let searchQuery = '';

async function syncDatabaseHistory() {
  try {
    const res = await fetch('/api/v1/history', {
      headers: { 'X-API-KEY': import.meta.env.VITE_API_KEY || '' } 
    });
    if (res.ok) {
      const data = await res.json();
      sessionHistory = data.entries.reverse();
      applyHistoryFilters();
    }
  } catch (err) {
    console.error("Database sync failed:", err);
  }
}
syncDatabaseHistory();

// PHASE 3: Filter Engine
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

// 4. EVENT LISTENERS

// Search & Filtering Listeners
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

dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => handleFile(e.target.files[0]));
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', e => { e.preventDefault(); dropZone.classList.remove('dragover'); });
dropZone.addEventListener('drop', e => { 
  e.preventDefault(); 
  dropZone.classList.remove('dragover'); 
  handleFile(e.dataTransfer.files[0]); 
});

// Tabbed Switching Logic
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-layer').forEach(l => l.classList.remove('active'));
    
    const targetId = e.target.dataset.target;
    e.target.classList.add('active');
    document.getElementById(targetId).classList.add('active');
  });
});

// Click-to-Reload History
historyList.addEventListener('click', (e) => {
  const item = e.target.closest('.hist-item');
  if (!item) return;

  const hash = item.dataset.hash;
  const entry = sessionHistory.find(x => x.file_sha256 === hash);
  
  if (entry) {
    document.querySelectorAll('.hist-item').forEach(el => el.classList.remove('active-log'));
    item.classList.add('active-log');

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
  gaugeFill.style.strokeDashoffset = 439.8;
  
  document.querySelectorAll('.hist-item').forEach(el => el.classList.remove('active-log'));
  document.getElementById('stat-score-sub').textContent = 'Pending';
  document.getElementById('stat-face-sub').textContent = 'Pending';
  document.getElementById('stat-qual-sub').textContent = 'Pending';
}

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

analyzeBtn.addEventListener('click', async () => {
  idleState.style.display = 'none';
  resultState.classList.add('visible');
  previewWrapper.classList.add('scanning');
  
  document.querySelector('[data-target="tab-source"]').click();
  
  setLoading(true);
  gaugeFill.style.strokeDashoffset = 439.8; 
  document.getElementById('low-conf-warning').style.display = 'none';
  document.getElementById('low-qual-warning').style.display = 'none';
  document.getElementById('warn-sys-error').classList.remove('visible');

  const fd = new FormData();
  fd.append('file', selectedFile);
  const explain = document.getElementById('explain-toggle').checked;

  try {
    const res = await fetch(`/api/v1/analyze?explain=${explain}`, { 
      method: 'POST', 
      body: fd, 
      headers: { 'X-API-KEY': import.meta.env.VITE_API_KEY || '' } 
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    
    previewWrapper.classList.remove('scanning');
    renderResult(data, selectedFile.name);
    
    sessionHistory.unshift({ timestamp: new Date().toISOString(), filename: selectedFile.name, ...data });
    applyHistoryFilters();
    
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
});

function renderResult(data, filename) {
  currentReport = { ...data, filename };
  const isFake = data.verdict === 'FAKE';
  const cls = isFake ? 'fake' : 'real';

  document.getElementById('trust-title').textContent = data.verdict;
  document.getElementById('trust-title').className = `trust-title title-${cls}`;
  document.getElementById('gauge-conf').textContent = `${data.confidence}%`;
  
  gaugeFill.className.baseVal = `gauge-fill ${cls}`;
  setTimeout(() => { gaugeFill.style.strokeDashoffset = 439.8 - (439.8 * (data.confidence / 100)); }, 100);

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

document.getElementById('clear-history-btn').addEventListener('click', () => {
  if (sessionHistory.length === 0) return;
  if (confirm("Clear the current session history view? (Note: Database logs remain securely stored in the backend)")) {
    sessionHistory = []; 
    applyHistoryFilters();
    idleState.style.display = 'flex'; resultState.classList.remove('visible'); selectedFile = null;
    analyzeBtn.textContent = 'AWAITING EVIDENCE'; analyzeBtn.disabled = true;
    gaugeFill.style.strokeDashoffset = 439.8;
  }
});

document.getElementById('export-btn').addEventListener('click', () => {
  if (!currentReport) return;
  const { jsPDF } = window.jspdf; 
  const doc = new jsPDF();
  doc.setFont("courier", "bold"); doc.setFontSize(22); doc.text("ViT-CORE Forensic Report", 20, 20);
  doc.setFontSize(12); doc.setFont("courier", "normal"); doc.text(`Generated: ${new Date().toLocaleString()}`, 20, 30); doc.line(20, 35, 190, 35);
  doc.setFont("courier", "bold"); doc.text("Media File Details", 20, 45);
  doc.setFont("courier", "normal"); doc.text(`Filename: ${currentReport.filename}`, 20, 55); doc.text(`Format: ${currentReport.type.toUpperCase()}`, 20, 65); doc.text(`Frames Analyzed: ${currentReport.frames_analyzed}`, 20, 75);
  doc.setFont("courier", "bold"); doc.text("Analysis Verdict", 20, 95);
  doc.setFont("courier", "normal"); doc.setTextColor(currentReport.verdict === 'FAKE' ? 255 : 0, 0, currentReport.verdict === 'REAL' ? 255 : 0); doc.text(`Verdict: ${currentReport.verdict}`, 20, 105); doc.setTextColor(0, 0, 0);
  doc.text(`Confidence: ${currentReport.confidence}%`, 20, 115); doc.text(`Raw Probability Score: ${currentReport.probability}`, 20, 125);
  doc.setFont("courier", "bold"); doc.text("Model Telemetry", 20, 145);
  doc.setFont("courier", "normal"); doc.text(`Face Detection Status: ${currentReport.face_detected ? 'Positive (MTCNN)' : 'Negative'}`, 20, 155); doc.text(`Face Quality Metrics: ${currentReport.face_quality}`, 20, 165); doc.text(`Processing Time: ${currentReport.processing_time_sec} sec`, 20, 175); doc.text(`Ambiguity Flag: ${currentReport.is_low_confidence ? 'FLAGGED - MANUAL REVIEW' : 'Clear'}`, 20, 185);
  doc.setFontSize(10); doc.setTextColor(100, 100, 100); doc.text("Disclaimer: Results are probabilistic and should be corroborated with other evidence.", 20, 280);
  doc.save(`ViT-CORE_Report_${currentReport.filename}.pdf`);
});
