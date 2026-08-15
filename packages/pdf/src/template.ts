export interface ReportPdfSection {
  key: string;
  title: string;
  body: string;
}

export interface ReportPdfData {
  assessmentName: string;
  profileName: string;
  profileDescription: string;
  sections: ReportPdfSection[];
  generatedAt: Date;
}

/**
 * Self-contained HTML — no external fonts/network requests, since this is
 * rendered headlessly. Mirrors the web report's design tokens
 * (packages/ui/src/tokens.css) so the PDF and in-browser report feel like
 * the same product, not a generic export.
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

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  @page { size: A4; margin: 0; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: #faf6ef;
    color: #1c1a17;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, system-ui, sans-serif;
    font-size: 12.5px;
    line-height: 1.6;
  }
  .page { padding: 56px 48px; }
  .eyebrow { font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: #78705f; margin: 0 0 12px; }
  h1 {
    font-family: Georgia, 'Iowan Old Style', 'Palatino Linotype', ui-serif, serif;
    font-size: 30px;
    line-height: 1.2;
    margin: 0 0 6px;
  }
  .subtitle { font-size: 14px; color: #4a453d; margin: 0 0 40px; }
  .section { margin: 0 0 28px; page-break-inside: avoid; }
  .section h2 {
    font-family: Georgia, 'Iowan Old Style', 'Palatino Linotype', ui-serif, serif;
    font-size: 17px;
    color: #6f342a;
    margin: 0 0 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid #e6dcc8;
  }
  .section p { margin: 0 0 8px; color: #2c2822; }
  .footer {
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #e6dcc8;
    font-size: 10px;
    color: #78705f;
    line-height: 1.5;
  }
</style>
</head>
<body>
  <div class="page">
    <p class="eyebrow">INNER — ${escapeHtml(data.assessmentName)}</p>
    <h1>${escapeHtml(data.profileName)}</h1>
    <p class="subtitle">${escapeHtml(data.profileDescription)}</p>

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

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
