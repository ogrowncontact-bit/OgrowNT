"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function QaRunTrigger() {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/qa/love/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count: 100 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to run QA simulation");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <button
        onClick={run}
        disabled={running}
        className="rounded-[var(--inner-radius-sm)] bg-[var(--inner-accent)] px-4 py-2 text-[13px] font-medium text-[var(--inner-accent-contrast)] disabled:opacity-50"
      >
        {running ? "Running 100 personas… (may take a minute)" : "Run new 100-persona simulation"}
      </button>
      {error && <p className="mt-2 text-[13px] text-[var(--inner-accent)]">{error}</p>}
    </div>
  );
}
