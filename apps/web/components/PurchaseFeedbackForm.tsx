"use client";

import { useState } from "react";

const REASONS: { value: string; label: string }[] = [
  { value: "curiosity", label: "Curiosity" },
  { value: "free_result_accurate", label: "The free result felt accurate" },
  { value: "wanted_more_detail", label: "I wanted more detail" },
  { value: "preview_convinced", label: "The preview convinced me" },
  { value: "price_reasonable", label: "Price felt reasonable" },
  { value: "other", label: "Other" },
];

/** FASE 33 §PURCHASE FEEDBACK — optional, shown once right after checkout succeeds; never blocks report access. */
export function PurchaseFeedbackForm({ orderId }: { orderId: string }) {
  const [reason, setReason] = useState<string | null>(null);
  const [otherText, setOtherText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(chosen: string, otherTextValue?: string) {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/orders/${orderId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: chosen, otherText: otherTextValue }),
      });
      if (!res.ok) throw new Error("Couldn't save that — please try again.");
      setSubmitted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  function choose(value: string) {
    setReason(value);
    if (value !== "other") submit(value);
  }

  if (submitted) {
    return (
      <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
        <p className="text-[14px] text-[var(--inner-ink-soft)]">Thanks — that helps us understand what mattered.</p>
      </div>
    );
  }

  return (
    <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
      <p className="text-[14px] font-medium text-[var(--inner-ink)]">What made you decide to unlock your report? (optional)</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {REASONS.map((r) => (
          <button
            key={r.value}
            type="button"
            onClick={() => choose(r.value)}
            className={`rounded-[var(--inner-radius-sm)] border px-3 py-2 text-[13px] ${
              reason === r.value
                ? "border-[var(--inner-accent)] bg-[var(--inner-accent)] text-[var(--inner-accent-contrast)]"
                : "border-[var(--inner-line)] text-[var(--inner-ink-soft)]"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      {reason === "other" && (
        <div className="mt-4">
          <textarea
            value={otherText}
            onChange={(e) => setOtherText(e.target.value)}
            rows={2}
            placeholder="Tell us a bit more (optional)"
            className="w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-paper)] px-3 py-2 text-[14px] text-[var(--inner-ink)]"
          />
          <button
            type="button"
            onClick={() => submit("other", otherText.trim() || undefined)}
            disabled={submitting}
            className="mt-3 rounded-[var(--inner-radius-sm)] bg-[var(--inner-accent)] px-4 py-2 text-[13px] font-medium text-[var(--inner-accent-contrast)] disabled:opacity-50"
          >
            {submitting ? "Sending…" : "Send"}
          </button>
        </div>
      )}
      {error && <p className="mt-2 text-[13px] text-[var(--inner-accent)]">{error}</p>}
    </div>
  );
}
