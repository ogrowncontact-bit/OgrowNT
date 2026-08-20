"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function PauseResumeButton({ paused }: { paused: boolean }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function handleClick() {
    let reason = "";
    if (!paused) {
      const input = window.prompt("Pause trading — why? (shown in the activity feed and audit trail)");
      if (input === null) return; // cancelled
      reason = input;
    } else if (!window.confirm("Resume trading?")) {
      return;
    }

    setPending(true);
    try {
      await fetch("/api/trading-pause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: paused ? "resume" : "pause", reason }),
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
        paused
          ? "border-signal-green/40 text-signal-green hover:bg-signal-green/10"
          : "border-signal-yellow/40 text-signal-yellow hover:bg-signal-yellow/10"
      }`}
    >
      {pending ? "Working…" : paused ? "Resume trading" : "Pause trading"}
    </button>
  );
}
