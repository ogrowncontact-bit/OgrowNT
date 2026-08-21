"use client";

import { useState } from "react";
import type { DemoPersona } from "@/lib/demoPersonas";

/**
 * FASE 29 §DEMO CONTROL — discreet, admin-only persona picker. Starts a real
 * assessment session (app/api/admin/demo/start), then opens the actual
 * public result page in a new tab so the founder can inspect it exactly as
 * a real visitor would see it, per persona.
 */
export function DemoPersonaPicker({ personas }: { personas: DemoPersona[] }) {
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function start(personaKey: string) {
    setPendingKey(personaKey);
    setError(null);
    try {
      const res = await fetch("/api/admin/demo/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ personaKey }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to start demo session");
      window.open(data.resultUrl, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setPendingKey(null);
    }
  }

  return (
    <div>
      {error && (
        <p role="alert" className="mb-4 rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-3 text-[13px] text-[var(--inner-ink)]">
          {error}
        </p>
      )}
      <div className="space-y-3">
        {personas.map((persona) => (
          <div key={persona.key} className="flex items-start justify-between gap-4 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4">
            <div>
              <p className="text-[14px] font-medium text-[var(--inner-ink)]">{persona.label}</p>
              <p className="mt-1 text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">{persona.summary}</p>
            </div>
            <button
              onClick={() => start(persona.key)}
              disabled={pendingKey !== null}
              className="shrink-0 rounded-[var(--inner-radius-sm)] bg-[var(--inner-accent)] px-3 py-1.5 text-[13px] font-medium text-[var(--inner-accent-contrast)] disabled:opacity-50"
            >
              {pendingKey === persona.key ? "Running…" : "Run demo"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
