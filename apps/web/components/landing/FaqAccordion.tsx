"use client";

import { useRef } from "react";
import type { FaqItem } from "@/lib/landingContent";
import { trackEvent } from "@/lib/clientTrack";

/**
 * Native <details>/<summary> per item — free keyboard nav, focus states,
 * and screen-reader semantics without a custom disclosure widget. Fires
 * faq_opened once per question per page load (not on every collapse/
 * re-expand toggle), so it reads as a real engagement signal.
 */
export function FaqAccordion({ items, assessmentId }: { items: FaqItem[]; assessmentId?: string }) {
  const openedRef = useRef<Set<string>>(new Set());

  function handleToggle(question: string, e: React.SyntheticEvent<HTMLDetailsElement>) {
    if (!e.currentTarget.open || openedRef.current.has(question)) return;
    openedRef.current.add(question);
    trackEvent("faq_opened", { question, assessmentId });
  }

  return (
    <div className="mt-4 divide-y divide-[var(--inner-line)]">
      {items.map((item) => (
        <details key={item.question} className="group py-4" onToggle={(e) => handleToggle(item.question, e)}>
          <summary className="cursor-pointer list-none text-[15px] font-medium text-[var(--inner-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--inner-accent)]">
            <span className="inline-block w-4 text-[var(--inner-muted)] group-open:hidden" aria-hidden>
              +
            </span>
            <span className="hidden w-4 text-[var(--inner-muted)] group-open:inline-block" aria-hidden>
              −
            </span>{" "}
            {item.question}
          </summary>
          <p className="mt-2 pl-6 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{item.answer}</p>
        </details>
      ))}
    </div>
  );
}
