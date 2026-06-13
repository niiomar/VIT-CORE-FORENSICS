export function renderSidebar() {
  return `
    <aside class="sidebar">
      <div class="brand">
        <div style="width:40px;height:40px;border-radius:8px;background:var(--blue);
                    display:flex;align-items:center;justify-content:center;
                    font-family:'Space Mono',monospace;font-weight:700;color:#fff;">VC</div>
        <div>
          <h1>VIT-CORE</h1>
          <p>Forensics // v2.0</p>
        </div>
      </div>

      <div class="session-stats">
        <div class="stat-box">
          <span>Total</span>
          <strong id="stat-total">0</strong>
        </div>
        <div class="stat-box">
          <span>Real</span>
          <strong id="stat-real-count" class="stat-real">0</strong>
        </div>
        <div class="stat-box">
          <span>Fake</span>
          <strong id="stat-fake-count" class="stat-fake">0</strong>
        </div>
      </div>

      <div id="drop-zone">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" stroke-width="1.5" style="margin:0 auto;display:block;">
          <path d="M12 16V4M12 4l-4 4M12 4l4 4" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <h2>Drop media file</h2>
        <p>or click to browse · image / video</p>
        <input type="file" id="file-input" accept="image/*,video/mp4,video/avi,video/quicktime,video/x-matroska,video/webm" style="display:none;">
      </div>

      <div class="explain-toggle-container">
        <input type="checkbox" id="explain-toggle" checked style="accent-color:var(--blue);width:16px;height:16px;cursor:pointer;">
        <label for="explain-toggle">Generate attention heatmap</label>
      </div>

      <button id="analyze-btn" class="action-btn" disabled>SELECT A FILE</button>

      <button id="export-btn" class="action-btn"
              style="background:var(--surface2);border:1px solid var(--border);margin-top:-12px;">
        EXPORT PDF REPORT
      </button>

      <div class="history-header">
        <span>Session History</span>
        <button id="clear-history-btn" class="clear-history">Clear</button>
      </div>
      <div class="history-list" id="history-list"></div>
    </aside>
  `;
}
