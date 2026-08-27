"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  initialPurchasesPaused: boolean;
  initialReportGenerationPaused: boolean;
  initialAiForceFallback: boolean;
}

/**
 * FASE 33 §EMERGENCY CONTROLS — admin kill switches, effective on the very
 * next request (see lib/emergencyControls.ts), no deploy required. "Disable
 * a specific assessment/product" is the existing publish/unpublish action on
 * /admin/assessments; "disable a specific question" is the per-question
 * toggle in the question editor — this panel only covers the three global
 * switches that don't already have a home.
 */
export function EmergencyControlsPanel({ initialPurchasesPaused, initialReportGenerationPaused, initialAiForceFallback }: Props) {
  const router = useRouter();
  const [purchasesPaused, setPurchasesPaused] = useState(initialPurchasesPaused);
  const [reportGenerationPaused, setReportGenerationPaused] = useState(initialReportGenerationPaused);
  const [aiForceFallback, setAiForceFallback] = useState(initialAiForceFallback);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(next: { purchasesPaused: boolean; reportGenerationPaused: boolean; aiForceFallback: boolean }) {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/emergency-controls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      });
      if (!res.ok) throw new Error("Couldn't save — please try again.");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  function Toggle({
    checked,
    onChange,
    label,
    description,
  }: {
    checked: boolean;
    onChange: (v: boolean) => void;
    label: string;
    description: string;
  }) {
    return (
      <label className="flex items-start justify-between gap-4 border-b border-[var(--inner-line)] py-3 last:border-0">
        <span>
          <span className="block text-[13px] font-medium text-[var(--inner-ink)]">{label}</span>
          <span className="block text-[12px] text-[var(--inner-muted)]">{description}</span>
        </span>
        <input
          type="checkbox"
          checked={checked}
          disabled={saving}
          onChange={(e) => {
            const next = {
              purchasesPaused: label === "Pause purchases" ? e.target.checked : purchasesPaused,
              reportGenerationPaused: label === "Pause report generation" ? e.target.checked : reportGenerationPaused,
              aiForceFallback: label === "Force AI fallback" ? e.target.checked : aiForceFallback,
            };
            onChange(e.target.checked);
            save(next);
          }}
          className="mt-1 h-5 w-9 shrink-0 cursor-pointer accent-[var(--inner-accent)]"
        />
      </label>
    );
  }

  return (
    <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
      <p className="text-[14px] font-medium text-[var(--inner-ink)]">Emergency controls</p>
      <p className="mt-1 text-[12px] text-[var(--inner-ink-soft)]">
        Effective on the next request — no deploy needed. Answers already saved are never lost while any of these are on.
      </p>
      <div className="mt-3">
        <Toggle
          checked={purchasesPaused}
          onChange={setPurchasesPaused}
          label="Pause purchases"
          description="New checkouts are blocked; anyone who already purchased keeps full access."
        />
        <Toggle
          checked={reportGenerationPaused}
          onChange={setReportGenerationPaused}
          label="Pause report generation"
          description="New report generation is held; retry it per-order from Reports once resumed."
        />
        <Toggle
          checked={aiForceFallback}
          onChange={setAiForceFallback}
          label="Force AI fallback"
          description="Every AI module uses its deterministic fallback content, even with a working API key."
        />
      </div>
      {error && <p className="mt-2 text-[13px] text-[var(--inner-accent)]">{error}</p>}
    </div>
  );
}
