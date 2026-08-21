"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

// "PROMPT 12" §61-62: only a human (admin) may begin/confirm kill-switch
// recovery — this button only ever calls the two admin-gated Next.js
// routes below, which in turn call the admin-gated FastAPI endpoints.
// Confirming without force requires the backend's own readiness check
// (system alive, no cadence failures) to pass; "Force confirm" is the
// explicit, itself-audited override for a human who has reviewed the
// situation and judges it safe anyway.
export function RecoveryButton({ killSwitchState }: { killSwitchState: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    const confirmed = window.confirm(
      "Start the kill switch recovery review? Trading stays disabled until you confirm recovery."
    );
    if (!confirmed) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/kill-switch-recovery-start", { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail ?? "Recovery start failed");
        return;
      }
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  async function confirm(force: boolean) {
    const confirmed = window.confirm(
      force
        ? "Force-confirm recovery despite a failed readiness check? Only do this after a manual review."
        : "Confirm recovery and re-enable trading?"
    );
    if (!confirmed) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/kill-switch-recovery-confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail ?? "Recovery confirm failed");
        return;
      }
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  if (killSwitchState === "locked") {
    return (
      <div className="flex flex-col items-end gap-1">
        <button
          onClick={start}
          disabled={pending}
          className="rounded border border-signal-yellow/40 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-signal-yellow transition hover:bg-signal-yellow/10 disabled:opacity-50"
        >
          {pending ? "Working…" : "Start recovery review"}
        </button>
        {error && <p className="text-[10px] text-signal-red">{error}</p>}
      </div>
    );
  }

  if (killSwitchState === "recovery") {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="flex gap-2">
          <button
            onClick={() => confirm(false)}
            disabled={pending}
            className="rounded border border-signal-green/40 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-signal-green transition hover:bg-signal-green/10 disabled:opacity-50"
          >
            {pending ? "Working…" : "Confirm recovery"}
          </button>
          <button
            onClick={() => confirm(true)}
            disabled={pending}
            className="rounded border border-signal-red/40 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-signal-red transition hover:bg-signal-red/10 disabled:opacity-50"
          >
            Force confirm
          </button>
        </div>
        {error && <p className="text-[10px] text-signal-red">{error}</p>}
      </div>
    );
  }

  return null;
}
