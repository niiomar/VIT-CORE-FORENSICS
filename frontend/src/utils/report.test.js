import { describe, it, expect, vi } from 'vitest';

const mockPdf = {
  setFont: vi.fn(),
  setFontSize: vi.fn(),
  text: vi.fn(),
  line: vi.fn(),
  setTextColor: vi.fn(),
  save: vi.fn(),
};

vi.mock('jspdf', () => ({
  // Must be a real function (not an arrow fn) so `new jsPDF()` in report.js works.
  default: vi.fn(function MockJsPDF() {
    return mockPdf;
  }),
}));

const { compilePdfReport } = await import('./report.js');

describe('compilePdfReport', () => {
  it('sanitizes unsafe filename characters and strips the extension before saving', () => {
    compilePdfReport({
      filename: 'evidence file (final)/v2.mp4',
      verdict: 'FAKE',
      confidence: 91.2,
      probability: 0.912,
      type: 'mp4',
      frames_analyzed: 5,
      processing_time_sec: 1.2,
      face_detected: true,
      face_quality: 'High',
      is_low_confidence: false,
    });

    expect(mockPdf.save).toHaveBeenCalledOnce();
    const savedName = mockPdf.save.mock.calls[0][0];
    expect(savedName).toMatch(/_forensics_report\.pdf$/);
    // No path separators, spaces, or parens should survive into a filename.
    expect(savedName).not.toMatch(/[\s/()]/);
  });

  it('does not throw when optional fields are missing', () => {
    expect(() => compilePdfReport({
      verdict: 'REAL',
      confidence: 50,
      probability: 0.5,
      type: 'jpg',
      frames_analyzed: 1,
      processing_time_sec: 0.1,
      face_detected: false,
      face_quality: 'N/A',
    })).not.toThrow();
  });
});
