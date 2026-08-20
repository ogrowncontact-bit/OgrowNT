"use client";

import { useState } from "react";
import type { AbandonmentRunResult } from "@/lib/assessmentAbandonment";

export function AbandonmentRunner() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AbandonmentRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/jobs/abandonment", { method: "POST" });
      if (!res.ok) throw new Error("Failed to run the sweep");
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
          <p className="font-display text-[16px] text-[var(--inner-ink)]">Abandoned session sweep</p>
          <p className="text-[13px] text-[var(--inner-ink-soft)]">
            Marks in-progress sessions with no activity for 2h+ as abandoned and records assessment_abandoned. In
            production this runs on a schedule — see CRON_SECRET in app/api/admin/jobs/abandonment/route.ts.
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
      {error && (
        <p role="alert" className="mt-3 text-[13px] text-[var(--inner-accent)]">
          {error}
        </p>
      )}
      {result && (
        <p className="mt-3 text-[13px] text-[var(--inner-ink-soft)]">
          {result.abandoned} marked abandoned, {result.stillActive} still within the activity window.
        </p>
      )}
    </div>
  );
}
