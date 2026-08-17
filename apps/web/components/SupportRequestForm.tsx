"use client";

import { useState } from "react";
import { Screen, Button } from "@inner/ui";

export function SupportRequestForm() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  async function handleSubmit() {
    if (!emailValid || submitting) return;
    setSubmitting(true);
    try {
      await fetch("/api/support/resend-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setDone(true);
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <Screen>
        <h1 className="font-display text-[24px] text-[var(--inner-ink)]">Check your inbox</h1>
        <p className="mt-3 text-[15px] text-[var(--inner-ink-soft)]">
          If that address has a purchased report on file, we've just resent it — give it a few minutes to arrive,
          and check spam if it doesn't show up.
        </p>
      </Screen>
    );
  }

  return (
    <Screen
      footer={
        <Button onClick={handleSubmit} disabled={!emailValid || submitting}>
          {submitting ? "..." : "Resend My Report"}
        </Button>
      }
    >
      <h1 className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">Didn't get your report?</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
        Enter the email you paid with and we'll resend your most recent purchased report.
      </p>

      <div className="mt-8">
        <label htmlFor="support-email" className="sr-only">
          Email
        </label>
        <input
          id="support-email"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-4 text-[16px] text-[var(--inner-ink)] placeholder:text-[var(--inner-muted)] focus:border-[var(--inner-accent)] focus:outline-none"
        />
      </div>
    </Screen>
  );
}
