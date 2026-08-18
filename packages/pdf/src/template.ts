export interface ReportPdfSection {
  key: string;
  title: string;
  body: string;
}

export interface ReportPdfDimension {
  key: string;
  label: string;
  normalized: number; // 0-100
}

export interface ReportPdfData {
  assessmentName: string;
  profileName: string;
  profileDescription: string;
  sections: ReportPdfSection[];
  /** Optional — omitted for assessments/report versions that don't carry dimension data. */
  dimensionScores?: ReportPdfDimension[];
  generatedAt: Date;
}

const BRAND_COLORS = {
  paper: "#faf6ef",
  ink: "#1c1a17",
  inkSoft: "#4a453d",
  muted: "#78705f",
  card: "#ffffff",
  line: "#e6dcc8",
  accent: "#6f342a",
  accentSoft: "#c98f73",
  accentContrast: "#fff7ef",
};

/**
 * Self-contained HTML — no external fonts/network requests, since this is
 * rendered headlessly. Mirrors the web report's design tokens
 * (packages/ui/src/tokens.css) so the PDF and in-browser report feel like
 * the same product: a private digital dossier, not a generic export.
 * Three explicit pages before content flows freely: cover, then a visual
 * signature/dimensions page, then the sections themselves.
 */
export function buildReportHtml(data: ReportPdfData): string {
  const sectionsHtml = data.sections
    .map(
      (s) => `
      <section class="section">
        <h2>${escapeHtml(s.title)}</h2>
        <p>${escapeHtml(s.body).replace(/\n\n+/g, "</p><p>").replace(/\n/g, "<br/>")}</p>
      </section>`
    )
    .join("\n");

  const dimensionsPageHtml =
    data.dimensionScores && data.dimensionScores.length > 0
      ? buildDimensionsPage(data)
      : "";

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  @page { size: A4; margin: 0; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: ${BRAND_COLORS.paper};
    color: ${BRAND_COLORS.ink};
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, system-ui, sans-serif;
    font-size: 12.5px;
    line-height: 1.6;
  }
  .page { padding: 56px 48px; }
  .page-break { page-break-after: always; }
  .eyebrow { font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: ${BRAND_COLORS.muted}; margin: 0 0 12px; }
  h1 {
    font-family: Georgia, 'Iowan Old Style', 'Palatino Linotype', ui-serif, serif;
    font-size: 30px;
    line-height: 1.2;
    margin: 0 0 6px;
  }
  .subtitle { font-size: 14px; color: ${BRAND_COLORS.inkSoft}; margin: 0 0 40px; }
  .section { margin: 0 0 28px; page-break-inside: avoid; }
  .section h2 {
    font-family: Georgia, 'Iowan Old Style', 'Palatino Linotype', ui-serif, serif;
    font-size: 17px;
    color: ${BRAND_COLORS.accent};
    margin: 0 0 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid ${BRAND_COLORS.line};
  }
  .section p { margin: 0 0 8px; color: #2c2822; }
  .footer {
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid ${BRAND_COLORS.line};
    font-size: 10px;
    color: ${BRAND_COLORS.muted};
    line-height: 1.5;
  }

  /* --- Cover page --- */
  .cover {
    height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 0 64px;
  }
  .cover .wordmark { font-size: 12px; letter-spacing: 0.35em; text-transform: uppercase; color: ${BRAND_COLORS.accent}; margin: 0 0 48px; font-weight: 600; }
  .cover .eyebrow { margin: 0 0 16px; }
  .cover h1 { font-size: 40px; margin: 0 0 24px; }
  .cover .signature-line { max-width: 420px; font-size: 15px; line-height: 1.7; color: ${BRAND_COLORS.inkSoft}; }
  .cover .rule { width: 48px; height: 2px; background: ${BRAND_COLORS.accentSoft}; margin: 32px 0; }

  /* --- Dimensions page --- */
  .dimensions-page { padding-top: 72px; }
  .dimensions-page h1 { font-size: 24px; margin-bottom: 8px; }
  .dimensions-page .intro { font-size: 13px; color: ${BRAND_COLORS.inkSoft}; margin: 0 0 40px; max-width: 480px; }
  .dim-row { display: flex; align-items: center; margin-bottom: 22px; page-break-inside: avoid; }
  .dim-label { width: 150px; flex-shrink: 0; font-size: 13px; font-weight: 500; color: ${BRAND_COLORS.ink}; }
  .dim-track { flex: 1; height: 8px; background: ${BRAND_COLORS.line}; border-radius: 4px; overflow: hidden; margin: 0 14px; }
  .dim-fill { height: 100%; background: ${BRAND_COLORS.accent}; border-radius: 4px; }
  .dim-score { width: 32px; flex-shrink: 0; text-align: right; font-size: 13px; font-variant-numeric: tabular-nums; color: ${BRAND_COLORS.muted}; }
</style>
</head>
<body>
  <div class="page cover page-break">
    <p class="wordmark">INNER</p>
    <p class="eyebrow">${escapeHtml(data.assessmentName)}</p>
    <h1>${escapeHtml(data.profileName)}</h1>
    <div class="rule"></div>
    <p class="signature-line">${escapeHtml(data.profileDescription)}</p>
  </div>

  ${dimensionsPageHtml}

  <div class="page">
    ${sectionsHtml}

    <div class="footer">
      Generated ${data.generatedAt.toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" })}.
      This is a personal reflection tool, not a clinical or diagnostic assessment. Your responses suggest
      patterns worth considering for your own reflection — they are not a fixed description of who you are,
      and INNER does not diagnose mental health, personality, or medical conditions.
    </div>
  </div>
</body>
</html>`;
}

function buildDimensionsPage(data: ReportPdfData): string {
  const rows = (data.dimensionScores ?? [])
    .slice()
    .sort((a, b) => b.normalized - a.normalized)
    .map(
      (d) => `
      <div class="dim-row">
        <div class="dim-label">${escapeHtml(d.label)}</div>
        <div class="dim-track"><div class="dim-fill" style="width: ${Math.max(0, Math.min(100, Math.round(d.normalized)))}%"></div></div>
        <div class="dim-score">${Math.round(d.normalized)}</div>
      </div>`
    )
    .join("\n");

  return `
  <div class="page dimensions-page page-break">
    <p class="eyebrow">Your INNER Signature</p>
    <h1>How your patterns measure</h1>
    <p class="intro">Every response contributes to a pattern across these dimensions — not a test score, a snapshot of tendencies that can shift with attention and circumstance.</p>
    ${rows}
  </div>`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
