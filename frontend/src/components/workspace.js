export function renderWorkspace() {
  return `
    <main class="main-view" id="main-view">

      <!-- IDLE -->
      <div id="idle-state">
        <div class="idle-shield">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="28" height="28"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
        </div>
        <p>AWAITING PROVENANCE TELEMETRY</p>
      </div>

      <!-- RESULT -->
      <div id="result-state">

        <!-- Warning banners -->
        <div class="warning-banner warn-amber" id="low-conf-warning">
          <svg class="banner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
          AMBIGUOUS TELEMETRY — Model confidence is low. Manual review recommended.
        </div>
        <div class="warning-banner warn-red" id="low-qual-warning">
          <svg class="banner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
          POOR EVIDENCE QUALITY — The detected face is highly degraded or blurry.
        </div>

        <!-- 1. Executive Panel -->
        <div class="executive-panel">
          <div class="exec-left">
            <div class="trust-ring-box">
              <svg class="gauge-svg" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="52" class="gauge-bg"></circle>
                <circle cx="60" cy="60" r="52" id="gauge-fill" class="gauge-fill"></circle>
              </svg>
              <div class="gauge-text">
                <span class="gauge-val" id="gauge-conf">0%</span>
                <span class="gauge-label">Conf</span>
              </div>
            </div>
            <div class="trust-info">
              <h2 class="trust-title" id="trust-title">UNKNOWN</h2>
              <p class="trust-sub">Model Verdict</p>
            </div>
          </div>
          
          <div class="exec-divider"></div>
          
          <div class="exec-right">
            <div class="tm-item">
              <span class="tm-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg> Agg. Probability</span>
              <strong class="tm-val" id="stat-score">0.0000</strong>
              <span class="tm-sub">Range 0.0 - 1.0</span>
            </div>
            <div class="tm-item">
              <span class="tm-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> Face Status</span>
              <strong class="tm-val" id="stat-face">N/A</strong>
              <span class="tm-sub">Detection Pipeline</span>
            </div>
            <div class="tm-item">
              <span class="tm-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 6.91 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg> Face Quality</span>
              <strong class="tm-val" id="stat-quality">N/A</strong>
              <span class="tm-sub">Worst Frame Evaluated</span>
            </div>
          </div>
        </div>

        <!-- 2. KPI Strip -->
        <div class="kpi-strip">
          <div class="kpi-item"><span class="kpi-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg> Format</span><span class="kpi-val" id="kpi-format">N/A</span></div>
          <div class="kpi-item"><span class="kpi-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg> Frames Extracted</span><span class="kpi-val" id="kpi-frames">0</span></div>
          <div class="kpi-item"><span class="kpi-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> Compute Time</span><span class="kpi-val" id="kpi-time">0s</span></div>
        </div>

        <!-- 3. Media Telemetry -->
        <div class="media-grid">
          <div class="media-panel" id="preview-wrapper">
            <div class="media-header"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg> Evidence Telemetry</div>
            <div class="media-content">
              <div class="scan-line"></div>
              <img id="preview-img" style="display:none;" />
              <video id="video-preview" controls style="display:none;"></video>
            </div>
          </div>

          <div class="media-panel" id="heatmap-wrapper">
            <div class="media-header"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg> Attention Rollout (ViT)</div>
            <div class="media-content">
              <div class="scan-line"></div>
              <img id="heatmap-img" />
            </div>
          </div>
        </div>

        <!-- 4. Export -->
        <div class="export-panel">
          <button id="export-btn" class="secondary-btn">Export Forensic Report (.PDF)</button>
        </div>

      </div>
    </main>
  `;
}
