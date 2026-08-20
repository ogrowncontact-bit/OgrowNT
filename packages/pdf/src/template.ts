import type { ReportDocument, ReportDocumentSection } from "@inner/ai";

export type { ReportDocument as ReportPdfData };

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
 * rendered headlessly. Mirrors apps/web/components/ReportView.tsx's
 * structure and role-based visual treatment (mirrored, not shared code,
 * since one is React/Tailwind for the browser and this is server-rendered
 * HTML for Playwright) so the PDF and in-browser report feel like the same
 * product: a private digital dossier, not a generic export. Both consume
 * the identical ReportDocument — see docs/ARCHITECTURE.md §7.
 */
export function buildReportHtml(doc: ReportDocument): string {
  const nonSignature = doc.sections.filter((s) => s.role !== "signature");
  const reflectionSection = nonSignature.find((s) => s.role === "reflection");
  const otherSections = nonSignature.filter((s) => s !== reflectionSection);
  const closingSection = otherSections.find((s) => s.role === "closing");
  const bodySections = otherSections.filter((s) => s !== closingSection);

  const sectionsHtml = bodySections.map(renderSection).join("\n");
  const dimensionsPageHtml = doc.dimensions.length > 0 ? buildDimensionsPage(doc) : "";
  const reflectionHtml = reflectionSection ? buildReflectionPage(reflectionSection, doc.reflectionQuestions) : "";
  const recommendationHtml = doc.recommendation ? buildRecommendationPage(doc.recommendation) : "";
  const closingHtml = closingSection ? buildClosingPage(closingSection) : "";

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
  .summary { font-family: Georgia, 'Iowan Old Style', 'Palatino Linotype', ui-serif, serif; font-size: 16px; font-style: italic; color: ${BRAND_COLORS.inkSoft}; line-height: 1.6; margin: 0 0 32px; }
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
  .section.card { background: ${BRAND_COLORS.card}; border: 1px solid ${BRAND_COLORS.line}; border-radius: 10px; padding: 18px 20px; }
  .section.card.strengths { border-left: 4px solid ${BRAND_COLORS.accent}; }
  .section.card.friction { border-left: 4px solid ${BRAND_COLORS.line}; }
  .section.core-pattern { border-left: 3px solid ${BRAND_COLORS.accent}; padding-left: 16px; }
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

  /* --- Reflection page --- */
  .reflection-list { list-style: none; margin: 20px 0 0; padding: 0; counter-reset: reflection; }
  .reflection-list li { counter-increment: reflection; margin-bottom: 16px; padding-left: 28px; position: relative; font-size: 14px; line-height: 1.6; color: ${BRAND_COLORS.ink}; }
  .reflection-list li::before { content: counter(reflection) "."; position: absolute; left: 0; color: ${BRAND_COLORS.accent}; font-weight: 600; }

  /* --- Recommendation page --- */
  .recommendation-page { display: flex; flex-direction: column; justify-content: center; height: 100vh; text-align: center; padding: 0 72px; }
  .recommendation-page .eyebrow { justify-content: center; }
  .recommendation-page p.bridge { font-family: Georgia, 'Iowan Old Style', 'Palatino Linotype', ui-serif, serif; font-size: 18px; font-style: italic; color: ${BRAND_COLORS.inkSoft}; line-height: 1.6; margin: 0 auto 20px; max-width: 420px; }
  .recommendation-page .cta { font-size: 14px; color: ${BRAND_COLORS.accent}; font-weight: 600; }

  /* --- Closing page --- */
  .closing-page { display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; text-align: center; padding: 0 80px; background: ${BRAND_COLORS.card}; }
  .closing-page p { font-family: Georgia, 'Iowan Old Style', 'Palatino Linotype', ui-serif, serif; font-size: 18px; font-style: italic; color: ${BRAND_COLORS.inkSoft}; line-height: 1.7; max-width: 440px; }
</style>
</head>
<body>
  <div class="page cover page-break">
    <p class="wordmark">INNER</p>
    <p class="eyebrow">${escapeHtml(doc.meta.assessmentName)}</p>
    <h1>${escapeHtml(doc.profile.name)}</h1>
    <div class="rule"></div>
    <p class="signature-line">${escapeHtml(doc.summary)}</p>
  </div>

  ${dimensionsPageHtml}

  <div class="page">
    ${sectionsHtml}

    <div class="footer">
      Generated ${new Date(doc.meta.generatedAt).toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" })}.
      This is a personal reflection tool, not a clinical or diagnostic assessment. Your responses suggest
      patterns worth considering for your own reflection — they are not a fixed description of who you are,
      and INNER does not diagnose mental health, personality, or medical conditions.
    </div>
  </div>

  ${reflectionHtml}
  ${recommendationHtml}
  ${closingHtml}
</body>
</html>`;
}

function renderSection(s: ReportDocumentSection): string {
  const cardClass = s.role === "strengths" ? "card strengths" : s.role === "friction" ? "card friction" : s.role === "tension" ? "card" : "";
  const classes = ["section", cardClass, s.role === "core_pattern" ? "core-pattern" : ""].filter(Boolean).join(" ");
  return `
      <section class="${classes}">
        <h2>${escapeHtml(s.title)}</h2>
        <p>${escapeHtml(s.body).replace(/\n\n+/g, "</p><p>").replace(/\n/g, "<br/>")}</p>
      </section>`;
}

function buildDimensionsPage(doc: ReportDocument): string {
  const rows = [...doc.dimensions]
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

function buildReflectionPage(section: ReportDocumentSection, questions: string[]): string {
  const items = questions.map((q) => `<li>${escapeHtml(q)}</li>`).join("\n");
  return `
  <div class="page page-break">
    <p class="eyebrow">${escapeHtml(section.title)}</p>
    <h1 style="font-size: 24px;">Questions worth sitting with</h1>
    ${section.body ? `<p class="subtitle" style="margin-bottom: 20px;">${escapeHtml(section.body)}</p>` : ""}
    <ol class="reflection-list">${items}</ol>
  </div>`;
}

function buildRecommendationPage(recommendation: NonNullable<ReportDocument["recommendation"]>): string {
  return `
  <div class="page recommendation-page page-break">
    <p class="eyebrow">Your Next Discovery</p>
    <p class="bridge">${escapeHtml(recommendation.bridgeCopy)}</p>
    <p class="cta">Continue Your Discovery: ${escapeHtml(recommendation.assessmentName)}</p>
  </div>`;
}

function buildClosingPage(section: ReportDocumentSection): string {
  return `
  <div class="page closing-page">
    <p>${escapeHtml(section.body)}</p>
  </div>`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
