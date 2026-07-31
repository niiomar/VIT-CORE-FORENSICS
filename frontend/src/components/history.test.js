import { describe, it, expect, beforeEach } from 'vitest';
import { renderHistoryItem, updateHistory } from './history.js';

describe('renderHistoryItem', () => {
  it('marks FAKE verdicts with the fake class and includes the filename', () => {
    const html = renderHistoryItem({
      verdict: 'FAKE', confidence: 92, filename: 'a.jpg',
      file_sha256: 'abc', timestamp: new Date().toISOString(),
    });
    expect(html).toContain('fake');
    expect(html).toContain('a.jpg');
  });

  it('marks REAL verdicts with the real class', () => {
    const html = renderHistoryItem({
      verdict: 'REAL', confidence: 80, filename: 'b.jpg',
      file_sha256: 'def', timestamp: new Date().toISOString(),
    });
    expect(html).toContain('real');
  });
});

describe('updateHistory', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="history-list"></div>
      <strong id="stat-total"></strong>
      <strong id="stat-real-count"></strong>
      <strong id="stat-fake-count"></strong>
    `;
  });

  it('shows a placeholder when there are no matching entries', () => {
    updateHistory([], []);
    expect(document.getElementById('history-list').textContent).toContain('NO LOGS MATCH QUERY');
  });

  it('computes real/fake counts from the full history, not just the filtered/displayed subset', () => {
    const full = [
      { verdict: 'REAL', confidence: 80, filename: 'a.jpg', file_sha256: '1', timestamp: new Date().toISOString() },
      { verdict: 'FAKE', confidence: 90, filename: 'b.jpg', file_sha256: '2', timestamp: new Date().toISOString() },
    ];
    // Simulate an active filter: only the FAKE entry is displayed, but
    // stats should still reflect the full history.
    const filtered = [full[1]];

    updateHistory(filtered, full);

    expect(document.getElementById('stat-total').textContent).toBe('2');
    expect(document.getElementById('stat-real-count').textContent).toBe('1');
    expect(document.getElementById('stat-fake-count').textContent).toBe('1');
    expect(document.getElementById('history-list').children).toHaveLength(1);
  });
});
