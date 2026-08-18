"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function StrategyActionButton({
  strategyId,
  action,
  label,
  confirmText,
}: {
  strategyId: number;
  action: "promote" | "restore";
  label: string;
  confirmText: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    if (!window.confirm(confirmText)) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/strategy-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategyId, action }),
      });
      const body = await res.json();
      if (!res.ok) {
        setError(body.detail ?? `${action} failed`);
        return;
      }
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <button
        onClick={handleClick}
        disabled={pending}
        className="rounded border border-signal-green/40 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-signal-green transition hover:bg-signal-green/10 disabled:opacity-50"
      >
        {pending ? "…" : label}
      </button>
      {error && <span className="text-[10px] text-signal-red">{error}</span>}
    </span>
  );
}
