"use client";

import { useState } from "react";

const CATEGORIES: { value: string; label: string }[] = [
  { value: "payment", label: "Payment issue" },
  { value: "report", label: "Report issue" },
  { value: "email", label: "Email issue" },
  { value: "technical", label: "Technical issue" },
  { value: "content", label: "Content issue" },
];

/** FASE 33 §SUPPORT — a separate, general issue-report form alongside the "resend my report" flow above it. No answer content is ever collected. */
export function IssueReportForm() {
  const [category, setCategory] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const canSubmit = category !== "" && emailValid && message.trim().length > 0 && !submitting;

  async function handleSubmit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/support/ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category, email, message: message.trim() }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? "Couldn't send that — please try again.");
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="mt-10 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
        <p className="text-[14px] text-[var(--inner-ink-soft)]">Thanks — we&apos;ve got it and will follow up by email.</p>
      </div>
    );
  }

  return (
    <div className="mt-10 border-t border-[var(--inner-line)] pt-8">
      <h2 className="font-display text-[20px] text-[var(--inner-ink)]">Something else wrong?</h2>
      <p className="mt-2 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">
        Tell us what happened and we&apos;ll follow up by email.
      </p>

      <div className="mt-5 space-y-3">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-3 text-[14px] text-[var(--inner-ink)]"
        >
          <option value="">What kind of issue?</option>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <input
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-3 text-[14px] text-[var(--inner-ink)] placeholder:text-[var(--inner-muted)]"
        />
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={4}
          placeholder="What happened?"
          className="w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-3 text-[14px] text-[var(--inner-ink)] placeholder:text-[var(--inner-muted)]"
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-5 py-3 text-[14px] font-medium text-[var(--inner-accent-contrast)] disabled:opacity-50"
        >
          {submitting ? "Sending…" : "Send"}
        </button>
        {error && <p className="text-[13px] text-[var(--inner-accent)]">{error}</p>}
      </div>
    </div>
  );
}
