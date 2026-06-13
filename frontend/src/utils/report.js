import jsPDF from 'jspdf';

export function compilePdfReport(report) {
  const pdf = new jsPDF();

  const {
    filename,
    verdict,
    confidence,
    probability,
    type,
    frames_analyzed,
    processing_time_sec,
    face_detected,
    face_quality
  } = report;

  let y = 20;

  pdf.setFontSize(20);
  pdf.text('VIT-CORE FORENSICS REPORT', 20, y);

  y += 15;
  pdf.setFontSize(12);

  const rows = [
    ['Filename', filename],
    ['Verdict', verdict],
    ['Confidence', `${confidence}%`],
    ['Probability Score', String(probability)],
    ['Media Type', String(type).toUpperCase()],
    ['Frames Analysed', String(frames_analyzed)],
    ['Processing Time', `${processing_time_sec}s`],
    ['Face Detected', face_detected ? 'Yes' : 'No'],
    ['Face Quality', face_quality]
  ];

  rows.forEach(([label, value]) => {
    pdf.text(`${label}: ${value}`, 20, y);
    y += 10;
  });

  y += 10;

  pdf.text(
    `Generated: ${new Date().toLocaleString()}`,
    20,
    y
  );

  const safeName =
    (filename || 'report')
      .replace(/[^\w.-]/g, '_')
      .replace(/\.[^.]+$/, '');

  pdf.save(`${safeName}_forensics_report.pdf`);
}