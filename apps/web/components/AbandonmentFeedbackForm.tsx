"use client";

import { useState } from "react";

const REASONS: { value: string; label: string }[] = [
  { value: "too_expensive", label: "Too expensive" },
  { value: "not_sure_useful", label: "Not sure it would be useful" },
  { value: "wanted_to_think", label: "Wanted to think about it" },
  { value: "not_enough_info", label: "Not enough information" },
  { value: "technical_problem", label: "Technical problem" },
  { value: "other", label: "Other" },
];

/**
 * FASE 33 §ABANDONMENT FEEDBACK — collapsed behind a low-key link by default
 * (never a popup), reveals a "what stopped you" chip picker on click.
 * Entirely optional — closing it or navigating away is always fine.
 */
export function AbandonmentFeedbackForm({ assessmentSessionId }: { assessmentSessionId: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<string | null>(null);
  const [otherText, setOtherText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function submit(chosen: string, otherTextValue?: string) {
    setSubmitting(true);
    try {
      const res = await fetch(`/api/sessions/${assessmentSessionId}/abandonment-feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: chosen, otherText: otherTextValue }),
      });
      if (res.ok) setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  }

  function choose(value: string) {
    setReason(value);
    if (value !== "other") submit(value);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-8 text-[13px] text-[var(--inner-muted)] underline underline-offset-4"
      >
        Not ready to unlock? Tell us why (optional)
      </button>
    );
  }

  if (submitted) {
    return (
      <p className="mt-8 text-[13px] text-[var(--inner-ink-soft)]">Thanks for letting us know.</p>
    );
  }

  return (
    <div className="mt-8 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
      <p className="text-[14px] font-medium text-[var(--inner-ink)]">What stopped you?</p>
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
            placeholder="Tell us more (optional)"
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
    </div>
  );
}
