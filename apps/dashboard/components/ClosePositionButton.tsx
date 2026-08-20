"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function ClosePositionButton({ positionId, assetSymbol }: { positionId: number; assetSymbol: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function handleClick() {
    const reason = window.prompt(`Close ${assetSymbol} at market now? Optionally note why:`);
    if (reason === null) return; // cancelled

    setPending(true);
    try {
      const res = await fetch("/api/trading-close-position", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ positionId, reason: reason || null }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        window.alert(body?.detail ?? "Close failed");
      }
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={pending}
      className="rounded border border-signal-red/40 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-signal-red transition hover:bg-signal-red/10 disabled:opacity-50"
    >
      {pending ? "…" : "Close"}
    </button>
  );
}
