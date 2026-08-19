"use client";

import { useState } from "react";
import Link from "next/link";
import { Screen, Button } from "@inner/ui";

export function AccessRequestForm() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  async function handleSubmit() {
    if (!emailValid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/access/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.status === 429) {
        const data = await res.json().catch(() => null);
        setError(data?.error ?? "Too many requests — please wait a few minutes and try again.");
        return;
      }
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
          If that address has purchased reports on file, we&apos;ve sent a link to access them — give it a few
          minutes to arrive, and check spam if it doesn&apos;t show up.
        </p>
      </Screen>
    );
  }

  return (
    <Screen
      footer={
        <Button onClick={handleSubmit} disabled={!emailValid || submitting}>
          {submitting ? "..." : "Send Access Link"}
        </Button>
      }
    >
      <h1 className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">Access your reports</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
        New device, or it&apos;s been a while? Enter the email you paid with and we&apos;ll send you a link to every
        INNER report you&apos;ve purchased.
      </p>

      <div className="mt-8">
        <label htmlFor="access-email" className="sr-only">
          Email
        </label>
        <input
          id="access-email"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-4 text-[16px] text-[var(--inner-ink)] placeholder:text-[var(--inner-muted)] focus:border-[var(--inner-accent)] focus:outline-none"
        />

        <p className="mt-4 text-xs leading-relaxed text-[var(--inner-muted)]">
          Only need your most recent report resent to the inbox you&apos;re already checking?{" "}
          <Link href="/support" className="underline">
            Use the quicker resend flow
          </Link>{" "}
          instead.
        </p>

        {error && (
          <p role="alert" className="mt-4 text-sm text-[var(--inner-accent)]">
            {error}
          </p>
        )}
      </div>
    </Screen>
  );
}
