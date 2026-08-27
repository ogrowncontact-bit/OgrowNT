"use client";

import { useState } from "react";
import type { CommandQueryResult } from "@/lib/api";

// Command Bar — "PROMPT 14" §91-93. QUERY/ANALYZE/EXPLAIN/SUMMARIZE only —
// NO DIRECT EXECUTION. Every submission goes through the same server-side
// safety classifier real trading actions are checked against
// (packages/system/command_router.py); this component has no code path
// that could execute a trade even if the classifier were somehow bypassed
// — it only ever renders whatever apps/api/routers/command_center.py
// returns, never calls order_manager or any execution code directly.
export function CommandBar() {
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<CommandQueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/command-query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const body = await res.json();
      if (!res.ok) {
        setError(body.detail ?? "Command rejected");
      } else {
        setResult(body as CommandQueryResult);
      }
    } catch {
      setError("Command bar unreachable");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Command Bar — query only, never executes</p>
      <form onSubmit={submit} className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. show me the best opportunities, or why is risk high?"
          className="flex-1 rounded border border-base-600 bg-base-950 px-3 py-1.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-ink-300 focus:outline-none"
        />
        <button
          type="submit"
          disabled={pending}
          className="rounded border border-base-600 px-3 py-1.5 text-xs uppercase text-ink-300 hover:bg-base-800 disabled:opacity-50"
        >
          {pending ? "…" : "Ask"}
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-signal-red">{error}</p>}
      {result && (
        <div className="mt-2 rounded border border-base-700/60 p-2.5">
          <p className="mb-1 text-[10px] uppercase text-ink-500">intent: {result.intent}</p>
          <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap text-[11px] text-ink-300">
            {result.data ? JSON.stringify(result.data, null, 2) : "No matching intent — try mentioning opportunities, risk, strategies, or blocked trades."}
          </pre>
        </div>
      )}
    </section>
  );
}
