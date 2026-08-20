"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function RestoreAgentButton({ code, name }: { code: string; name: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function handleClick() {
    if (!window.confirm(`Restore ${name} from quarantine? It rejoins the Consensus Engine's vote immediately.`)) return;
    setPending(true);
    try {
      await fetch("/api/agent-restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
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
      className="rounded border border-signal-green/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-signal-green transition hover:bg-signal-green/10 disabled:opacity-50"
    >
      {pending ? "Working…" : "Restore"}
    </button>
  );
}
