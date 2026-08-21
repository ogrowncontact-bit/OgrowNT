"use client";

import { useState } from "react";

const RATINGS: { value: string; label: string }[] = [
  { value: "very_accurate", label: "Very accurate" },
  { value: "mostly_accurate", label: "Mostly accurate" },
  { value: "somewhat_accurate", label: "Somewhat accurate" },
  { value: "not_very_accurate", label: "Not very accurate" },
  { value: "not_accurate", label: "Not accurate" },
];

/** FASE 32 §FEEDBACK — always optional, never blocks or gates anything else on the report page. */
export function ReportFeedbackForm({ reportId }: { reportId: string }) {
  const [rating, setRating] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [showComment, setShowComment] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(chosen: string, commentText?: string) {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/reports/${reportId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating: chosen, comment: commentText }),
      });
      if (!res.ok) throw new Error("Couldn't save your feedback — please try again.");
      setSubmitted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  function choose(value: string) {
    setRating(value);
    setShowComment(true);
  }

  if (submitted) {
    return (
      <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
        <p className="text-[14px] text-[var(--inner-ink-soft)]">Thank you — that helps us improve future reports.</p>
      </div>
    );
  }

  return (
    <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
      <p className="text-[14px] font-medium text-[var(--inner-ink)]">Did this feel accurate to you?</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {RATINGS.map((r) => (
          <button
            key={r.value}
            type="button"
            onClick={() => choose(r.value)}
            className={`rounded-[var(--inner-radius-sm)] border px-3 py-2 text-[13px] ${
              rating === r.value
                ? "border-[var(--inner-accent)] bg-[var(--inner-accent)] text-[var(--inner-accent-contrast)]"
                : "border-[var(--inner-line)] text-[var(--inner-ink-soft)]"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      {showComment && rating && (
        <div className="mt-4">
          <label htmlFor="feedback-comment" className="mb-2 block text-[13px] text-[var(--inner-ink-soft)]">
            What felt most accurate? (optional)
          </label>
          <textarea
            id="feedback-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            className="w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-paper)] px-3 py-2 text-[14px] text-[var(--inner-ink)]"
          />
          <button
            type="button"
            onClick={() => submit(rating, comment.trim() || undefined)}
            disabled={submitting}
            className="mt-3 rounded-[var(--inner-radius-sm)] bg-[var(--inner-accent)] px-4 py-2 text-[13px] font-medium text-[var(--inner-accent-contrast)] disabled:opacity-50"
          >
            {submitting ? "Sending…" : "Send feedback"}
          </button>
          {error && <p className="mt-2 text-[13px] text-[var(--inner-accent)]">{error}</p>}
        </div>
      )}
    </div>
  );
}
