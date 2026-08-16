"use client";

import { useState } from "react";
import type { ReengagementRunResult } from "@/lib/reengagement";

export function ReengagementRunner() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ReengagementRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/jobs/reengagement", { method: "POST" });
      if (!res.ok) throw new Error("Failed to run the batch");
      setResult(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="mb-8 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-display text-[16px] text-[var(--inner-ink)]">Re-engagement emails</p>
          <p className="text-[13px] text-[var(--inner-ink-soft)]">
            Checkout reminders (1h after checkout without payment) and post-purchase recommendation nudges (1 day
            after purchase, consent-gated). In production this runs on a schedule — see CRON_SECRET in
            app/api/admin/jobs/reengagement/route.ts.
          </p>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="shrink-0 rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[13px] text-[var(--inner-ink-soft)] hover:border-[var(--inner-accent-soft)] disabled:opacity-40"
        >
          {running ? "Running..." : "Run now"}
        </button>
      </div>
      {error && <p className="mt-3 text-[13px] text-[var(--inner-accent)]">{error}</p>}
      {result && (
        <p className="mt-3 text-[13px] text-[var(--inner-ink-soft)]">
          Checkout reminders: {result.checkoutReminders.sent} sent, {result.checkoutReminders.skipped} skipped.
          Recommendation nudges: {result.recommendationNudges.sent} sent, {result.recommendationNudges.skipped}{" "}
          skipped.
        </p>
      )}
    </div>
  );
}
