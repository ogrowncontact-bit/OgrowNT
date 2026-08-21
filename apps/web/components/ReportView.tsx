import type { ReportDocument, ReportDocumentSection } from "@inner/ai";

interface ReportViewProps {
  assessmentLabel: string;
  document: ReportDocument;
  /**
   * Left to the caller rather than rendered here: the web page tracks a
   * click (RecommendationLink) and recomputes the recommendation live so
   * "already completed" filtering stays fresh, while a PDF-preview caller
   * can pass nothing or a static block built from document.recommendation
   * (the generation-time snapshot). Positioned right before the closing
   * section, matching the report's existing layout.
   */
  recommendationSlot?: React.ReactNode;
}

export const CARD = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-6";
export const EYEBROW = "mb-2 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]";

/**
 * The single renderer both the web report page and (via packages/pdf's
 * template, which mirrors this component's structure in server-rendered
 * HTML rather than React) the PDF consume — see docs/ARCHITECTURE.md §7's
 * "Do not create separate logic for web report and PDF report." Sections
 * are rendered in their authored order; each gets a visual treatment based
 * on its `role` rather than the document repeating the same observation
 * once as a teaser and again as a dedicated section.
 */
export function ReportView({ assessmentLabel, document, recommendationSlot }: ReportViewProps) {
  const nonSignatureSections = document.sections.filter((s) => s.role !== "signature");
  const reflectionSection = nonSignatureSections.find((s) => s.role === "reflection");
  const otherSections = nonSignatureSections.filter((s) => s !== reflectionSection);
  const closingSection = otherSections.find((s) => s.role === "closing");
  const bodySections = otherSections.filter((s) => s !== closingSection);

  return (
    <div>
      <p className={EYEBROW}>{assessmentLabel} — Full Report</p>
      <h1 className="font-display text-[30px] leading-tight text-[var(--inner-ink)]">{document.profile.name}</h1>

      <p className="mt-6 font-display text-[18px] leading-relaxed text-[var(--inner-ink-soft)]">{document.summary}</p>

      {document.dimensions.length > 0 && (
        <div className="mt-10">
          <p className={EYEBROW}>Your Dimensions</p>
          <p className="mb-5 text-[12px] text-[var(--inner-muted)]">Relative pattern based on your responses — not a clinical measurement.</p>
          <div className="space-y-3">
            {[...document.dimensions]
              .sort((a, b) => b.normalized - a.normalized)
              .map((d) => (
                <div key={d.key} className="flex items-center gap-3">
                  <span className="w-32 shrink-0 text-[13px] font-medium text-[var(--inner-ink)]">{d.label}</span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--inner-line)]">
                    <span className="block h-full rounded-full bg-[var(--inner-accent)]" style={{ width: `${Math.max(0, Math.min(100, Math.round(d.normalized)))}%` }} />
                  </span>
                  <span className="w-8 shrink-0 text-right text-[13px] tabular-nums text-[var(--inner-muted)]">{Math.round(d.normalized)}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      <div className="mt-10 space-y-6">
        {bodySections.map((section) => (
          <ReportSectionBlock key={section.key} section={section} />
        ))}
      </div>

      {reflectionSection && (
        <div className="mt-10">
          <h2 className="font-display text-[19px] text-[var(--inner-accent)]">{reflectionSection.title}</h2>
          {reflectionSection.body && <p className="mt-2 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{reflectionSection.body}</p>}
          {document.reflectionQuestions.length > 0 && (
            <ol className="mt-4 space-y-3">
              {document.reflectionQuestions.map((q, i) => (
                <li key={i} className="flex gap-3 text-[15px] leading-relaxed text-[var(--inner-ink)]">
                  <span className="text-[var(--inner-accent)]">{i + 1}.</span>
                  <span>{q}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {recommendationSlot}

      {closingSection && (
        <div className={`${CARD} mt-10 bg-[var(--inner-paper)]`}>
          <p className="text-[15px] italic leading-relaxed text-[var(--inner-ink-soft)]">{closingSection.body}</p>
        </div>
      )}
    </div>
  );
}

/** Exported for app/[slug]/session/[id]/report-preview/page.tsx — the same real per-section visual treatment, reused rather than reinvented for a smaller, pre-purchase set of sections. */
export function ReportSectionBlock({ section }: { section: ReportDocumentSection }) {
  if (section.role === "core_pattern") {
    return (
      <div className="border-l-2 border-[var(--inner-accent)] pl-4">
        <h2 className="font-display text-[19px] text-[var(--inner-accent)]">{section.title}</h2>
        <p className="mt-2 text-[16px] leading-relaxed text-[var(--inner-ink)]">{section.body}</p>
      </div>
    );
  }

  if (section.role === "tension") {
    return (
      <div className={CARD}>
        <p className={EYEBROW}>{section.title}</p>
        <p className="text-[15px] leading-relaxed text-[var(--inner-ink)]">{section.body}</p>
      </div>
    );
  }

  if (section.role === "strengths" || section.role === "friction") {
    const accent = section.role === "strengths" ? "border-[var(--inner-accent)]" : "border-[var(--inner-line)]";
    return (
      <div className={`rounded-[var(--inner-radius-lg)] border-l-4 ${accent} border-y border-r border-[var(--inner-line)] bg-[var(--inner-card)] p-5`}>
        <p className="mb-1.5 text-[13px] font-medium text-[var(--inner-ink)]">{section.title}</p>
        <p className="text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{section.body}</p>
      </div>
    );
  }

  if (section.role === "how_you_come_across" || section.role === "under_pressure") {
    return (
      <div>
        <p className={EYEBROW}>{section.title}</p>
        <p className="text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{section.body}</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="font-display text-[19px] text-[var(--inner-accent)]">{section.title}</h2>
      <p className="mt-2 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">{section.body}</p>
    </div>
  );
}
