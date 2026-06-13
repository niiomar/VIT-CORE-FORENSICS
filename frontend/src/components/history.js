export function updateHistoryLayout(history = []) {
  const historyList = document.getElementById('history-list');
  const totalEl = document.getElementById('stat-total');
  const realEl = document.getElementById('stat-real-count');
  const fakeEl = document.getElementById('stat-fake-count');

  if (!historyList) return;

  const total = history.length;
  const realCount = history.filter(
    item => String(item.verdict).toUpperCase() === 'REAL'
  ).length;
  const fakeCount = history.filter(
    item => String(item.verdict).toUpperCase() === 'FAKE'
  ).length;

  if (totalEl) totalEl.textContent = total;
  if (realEl) realEl.textContent = realCount;
  if (fakeEl) fakeEl.textContent = fakeCount;

  if (total === 0) {
    historyList.innerHTML = `
      <div class="history-empty">
        No analyses recorded
      </div>
    `;
    return;
  }

  historyList.innerHTML = history
    .slice()
    .reverse()
    .map(entry => {
      const verdict = entry.verdict || 'UNKNOWN';
      const confidence = entry.confidence ?? 0;
      const filename = entry.filename || 'unnamed-file';

      return `
        <div class="history-item">
          <div class="history-item-top">
            <span class="history-file">${filename}</span>
            <span class="history-verdict ${verdict.toLowerCase()}">
              ${verdict}
            </span>
          </div>

          <div class="history-item-bottom">
            <span>${confidence}%</span>
            <span>${new Date(entry.timestamp).toLocaleString()}</span>
          </div>
        </div>
      `;
    })
    .join('');
}