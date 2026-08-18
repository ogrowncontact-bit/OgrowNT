"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function KillSwitchButton({ tradingEnabled }: { tradingEnabled: boolean }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function handleClick() {
    const action = tradingEnabled ? "trigger" : "release";
    const confirmed = window.confirm(
      action === "trigger"
        ? "Pull the kill switch? This immediately disables new trading (open positions still monitored)."
        : "Release the kill switch and re-enable trading?"
    );
    if (!confirmed) return;

    setPending(true);
    try {
      await fetch("/api/kill-switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={pending}
      className={`rounded border px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition disabled:opacity-50 ${
        tradingEnabled
          ? "border-signal-red/40 text-signal-red hover:bg-signal-red/10"
          : "border-signal-green/40 text-signal-green hover:bg-signal-green/10"
      }`}
    >
      {pending ? "Working…" : tradingEnabled ? "Pull kill switch" : "Release kill switch"}
    </button>
  );
}
