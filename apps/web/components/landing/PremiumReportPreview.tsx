"use client";

import { useEffect, useRef } from "react";
import { formatPrice } from "@/lib/money";
import { trackEvent } from "@/lib/clientTrack";

interface Props {
  items: string[];
  priceCents: number;
  currency: string;
  assessmentId?: string;
}

/** FASE 23 §PREMIUM REPORT SECTION — real structure (see lib/landingContent.ts's getPremiumPreviewItems), never a fabricated page count. Fires premium_preview_viewed once, the first time this section actually scrolls into view. */
export function PremiumReportPreview({ items, priceCents, currency, assessmentId }: Props) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let fired = false;
    const observer = new IntersectionObserver(
      (entries) => {
        if (fired) return;
        for (const entry of entries) {
          if (entry.isIntersecting) {
            fired = true;
            trackEvent("premium_preview_viewed", { assessmentId });
            observer.disconnect();
          }
        }
      },
      { threshold: 0.4 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [assessmentId]);

  return (
    <section ref={ref} className="mt-12 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-6">
      <p className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--inner-muted)]">Inside the complete report</p>
      <p className="font-display mt-2 text-[24px] text-[var(--inner-ink)]">{formatPrice(priceCents, currency)}</p>
      <ul className="mt-4 space-y-2">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-3 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">
            <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--inner-accent)]" />
            {item}
          </li>
        ))}
      </ul>
      <p className="mt-4 text-[13px] leading-relaxed text-[var(--inner-muted)]">
        Available as a private web page and a downloadable PDF, both yours to keep.
      </p>
    </section>
  );
}
