import { describe, it, expect, vi, beforeEach } from 'vitest';
import { executeForensicAnalysis, executeBatchAnalysis, fetchHistory } from './api.js';

describe('executeForensicAnalysis', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('returns parsed JSON on success', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ verdict: 'REAL' }),
    });

    const file = new File(['x'], 'test.jpg', { type: 'image/jpeg' });
    const result = await executeForensicAnalysis(file, true, vi.fn());

    expect(result).toEqual({ verdict: 'REAL' });
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/analyze?explain=true'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('calls onThrottled and returns null on 429 instead of throwing', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 429 });
    const onThrottled = vi.fn();

    const file = new File(['x'], 'test.jpg', { type: 'image/jpeg' });
    const result = await executeForensicAnalysis(file, false, onThrottled);

    expect(result).toBeNull();
    expect(onThrottled).toHaveBeenCalledOnce();
  });

  it('throws a clear error on 401', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 401 });
    const file = new File(['x'], 'test.jpg', { type: 'image/jpeg' });

    await expect(executeForensicAnalysis(file, false, vi.fn())).rejects.toThrow(/Unauthorized/);
  });

  it('surfaces the server-provided detail message on other failures', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Unsupported media format' }),
    });
    const file = new File(['x'], 'test.jpg', { type: 'image/jpeg' });

    await expect(executeForensicAnalysis(file, false, vi.fn())).rejects.toThrow('Unsupported media format');
  });
});

describe('executeBatchAnalysis', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('posts every file to the batch endpoint', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ summary: { total: 2 }, results: [] }),
    });

    const files = [new File(['a'], 'a.jpg'), new File(['b'], 'b.jpg')];
    const result = await executeBatchAnalysis(files, vi.fn());

    expect(result.summary.total).toBe(2);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/analyze/batch'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('calls onThrottled and returns null on 429', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 429 });
    const onThrottled = vi.fn();

    const result = await executeBatchAnalysis([new File(['a'], 'a.jpg')], onThrottled);

    expect(result).toBeNull();
    expect(onThrottled).toHaveBeenCalledOnce();
  });
});

describe('fetchHistory', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('returns entries on success', async () => {
    global.fetch.mockResolvedValue({ ok: true, json: async () => ({ entries: [{ id: 1 }] }) });
    const result = await fetchHistory();
    expect(result.entries).toHaveLength(1);
  });

  it('falls back to an empty list instead of throwing on failure', async () => {
    global.fetch.mockResolvedValue({ ok: false });
    const result = await fetchHistory();
    expect(result).toEqual({ entries: [] });
  });
});
