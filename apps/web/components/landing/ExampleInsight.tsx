/**
 * FASE 23 §EXAMPLE INSIGHT — an illustrative preview, clearly labeled and
 * never implying it belongs to the visitor. Only renders when an admin has
 * actually written one via the assessment's "Landing Page" CMS section
 * (AssessmentEditor.tsx) — no fabricated example if none is configured.
 */
export function ExampleInsight({ text }: { text: string }) {
  return (
    <section className="mt-12 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-paper-dim)] p-6">
      <p className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--inner-accent)]">Example Insight</p>
      <p className="mt-3 text-[15px] italic leading-relaxed text-[var(--inner-ink)]">&ldquo;{text}&rdquo;</p>
      <p className="mt-4 text-[13px] leading-relaxed text-[var(--inner-muted)]">
        This is an illustrative example, not your result. INNER explores interactions between patterns rather than
        fixed labels — your own answers shape what you&apos;ll actually see.
      </p>
    </section>
  );
}
