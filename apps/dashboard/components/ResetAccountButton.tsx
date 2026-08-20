"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function ResetAccountButton({ openPositionsCount }: { openPositionsCount: number }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function handleClick() {
    if (openPositionsCount > 0) {
      window.alert(`${openPositionsCount} open position(s) must be closed first.`);
      return;
    }
    const typed = window.prompt('Type "RESET" to wipe the paper account back to its configured starting capital:');
    if (typed !== "RESET") return;

    setPending(true);
    try {
      const res = await fetch("/api/trading-reset", { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        window.alert(body?.detail ?? "Reset failed");
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
      className="rounded border border-base-700 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-ink-300 transition hover:bg-base-800 disabled:opacity-50"
      title="Requires confirmation and zero open positions"
    >
      {pending ? "Working…" : "Reset paper account"}
    </button>
  );
}
