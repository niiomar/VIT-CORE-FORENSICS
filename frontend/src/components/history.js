export function renderHistoryItem(item) {
  const isFake = item.verdict === 'FAKE';
  const cls = isFake ? 'fake' : 'real';

  return `
    <div class="hist-item ${cls}" data-hash="${item.file_sha256 || ''}">
      <div class="hi-top">
        <span class="hist-badge ${cls}">${item.verdict}</span>
        <span class="hi-conf">${item.confidence}%</span>
      </div>
      <div class="hi-bot">
        <span class="hi-name" title="${item.filename}">${item.filename}</span>
        <span class="hi-time">${new Date(item.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
      </div>
    </div>
  `;
}

export function updateHistory(sessionHistory) {
  const list = document.getElementById('history-list');
  if (!list) return;
  
  list.innerHTML = '';
  let fakes = 0; let reals = 0;
  
  sessionHistory.forEach(item => {
    const isFake = item.verdict === 'FAKE';
    isFake ? fakes++ : reals++;
    list.innerHTML += renderHistoryItem(item);
  });
  
  document.getElementById('stat-total').textContent = sessionHistory.length;
  document.getElementById('stat-real-count').textContent = reals;
  document.getElementById('stat-fake-count').textContent = fakes;
}
