export function renderWorkspace() {
  return `
    <main class="main-view">

      <style>
        /* Scoped additions — not yet present in styles.css */
        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          width: 100%;
          margin-top: 24px;
        }
        .metric-box {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 14px 16px;
        }
        .metric-box span {
          display: block;
          font-size: 10px;
          color: var(--text-dim);
          text-transform: uppercase;
          letter-spacing: 0.1em;
          margin-bottom: 6px;
        }
        .metric-box strong {
          font-family: 'Space Mono', monospace;
          font-size: 16px;
          color: var(--text-hi);
        }
        .warning-banner {
          display: none;
          align-items: center;
          gap: 10px;
          width: 100%;
          padding: 12px 16px;
          border-radius: 8px;
          font-size: 12px;
          font-family: 'Space Mono', monospace;
          margin-bottom: 16px;
          border: 1px solid;
        }
        #rate-limit-warning { background: rgba(248,81,73,.08); border-color: var(--red); color: var(--red); }
        #low-conf-warning   { background: rgba(210,153,34,.08); border-color: var(--amber); color: var(--amber); }
        #low-qual-warning   { background: rgba(210,153,34,.08); border-color: var(--amber); color: var(--amber); }
      </style>

      <!-- IDLE STATE -->
      <div id="idle-state">
        <div class="idle-eye"></div>
        <p>AWAITING MEDIA INPUT</p>
      </div>

      <!-- RESULT STATE -->
      <div id="result-state">

        <div id="rate-limit-warning" class="warning-banner">
          ⚠ RATE LIMIT REACHED — cooling down before retry is allowed.
        </div>
        <div id="low-conf-warning" class="warning-banner">
          ⚠ LOW CONFIDENCE — result falls in the ambiguous 40–60% range. Treat as inconclusive.
        </div>
        <div id="low-qual-warning" class="warning-banner">
          ⚠ POOR FACE QUALITY — blur or exposure issues detected; result reliability is reduced.
        </div>

        <div class="top-stats">

          <div class="gauge-container">
            <svg class="gauge-svg" viewBox="0 0 160 160">
              <circle class="gauge-bg" cx="80" cy="80" r="70"></circle>
              <circle id="gauge-fill" class="gauge-fill real" cx="80" cy="80" r="70"></circle>
            </svg>
            <div class="gauge-text">
              <div class="verdict" id="gauge-verdict">—</div>
              <div class="conf"><span id="gauge-conf">0</span>% CONFIDENCE</div>
            </div>
          </div>

          <div class="workspace-panels">
            <div class="preview-container" id="preview-wrapper">
              <div class="scan-line"></div>
              <span class="panel-title">SOURCE</span>
              <img id="preview-img" src="" alt="preview" style="display:none;">
              <video id="video-preview" muted playsinline controls style="display:none;"></video>
            </div>
            <div class="preview-container" id="heatmap-wrapper">
              <div class="scan-line"></div>
              <span class="panel-title">ATTENTION ROLLOUT</span>
              <img id="heatmap-img" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" alt="heatmap">
            </div>
          </div>

        </div>

        <div class="metrics-grid">
          <div class="metric-box"><span>Probability Score</span><strong id="stat-score">0.000</strong></div>
          <div class="metric-box"><span>Media Type</span><strong id="stat-type">—</strong></div>
          <div class="metric-box"><span>Frames Analyzed</span><strong id="stat-frames">0</strong></div>
          <div class="metric-box"><span>Face Detection</span><strong id="stat-face">—</strong></div>
          <div class="metric-box"><span>Face Quality</span><strong id="stat-quality">—</strong></div>
          <div class="metric-box"><span>Processing Time</span><strong id="stat-time">0s</strong></div>
        </div>

      </div>

    </main>
  `;
}
