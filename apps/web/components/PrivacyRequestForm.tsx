"use client";

import { useState } from "react";
import { Screen, Button } from "@inner/ui";

export function PrivacyRequestForm() {
  const [email, setEmail] = useState("");
  const [action, setAction] = useState<"export" | "delete">("export");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  async function handleSubmit() {
    if (!emailValid || submitting) return;
    setSubmitting(true);
    try {
      await fetch("/api/privacy/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, action }),
      });
      setDone(true);
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <Screen>
        <h1 className="font-display text-[24px] text-[var(--inner-ink)]">Check your email</h1>
        <p className="mt-3 text-[15px] text-[var(--inner-ink-soft)]">
          If we have data on file for that address, we've sent a confirmation link. Nothing happens until you click
          it and confirm — the link doesn't act by itself.
        </p>
      </Screen>
    );
  }

  return (
    <Screen
      footer={
        <Button onClick={handleSubmit} disabled={!emailValid || submitting}>
          {submitting ? "..." : "Send Confirmation Link"}
        </Button>
      }
    >
      <h1 className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">Your data, your choice</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
        Request a copy of everything INNER has on file for you, or ask us to delete it. We'll email a confirmation
        link to the address you paid with — nothing happens until you click it.
      </p>

      <div className="mt-8">
        <input
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-4 text-[16px] text-[var(--inner-ink)] placeholder:text-[var(--inner-muted)] focus:border-[var(--inner-accent)] focus:outline-none"
        />

        <div className="mt-5 flex gap-3">
          <label className="flex flex-1 items-center gap-2 rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] p-3 text-[14px] text-[var(--inner-ink)]">
            <input type="radio" name="action" checked={action === "export"} onChange={() => setAction("export")} />
            Export my data
          </label>
          <label className="flex flex-1 items-center gap-2 rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] p-3 text-[14px] text-[var(--inner-ink)]">
            <input type="radio" name="action" checked={action === "delete"} onChange={() => setAction("delete")} />
            Delete my data
          </label>
        </div>

        {action === "delete" && (
          <p className="mt-4 text-xs leading-relaxed text-[var(--inner-muted)]">
            This permanently erases your assessment answers and account. Purchase records are kept in anonymized
            form only where required by law.
          </p>
        )}
      </div>
    </Screen>
  );
}
