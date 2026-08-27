"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Incident } from "@/lib/api";

// Incident Center — "PROMPT 14" §59-62. Incidents are auto-created by
// apps/api/realtime.py's tail loop (packages/events/tailer.py) from this
// system's own existing critical-event detectors; this panel is purely the
// §61 lifecycle workflow on top of that (detected -> investigating ->
// mitigated -> recovering -> resolved -> closed), enforced server-side
// (apps/api/routers/incidents.py rejects any backward transition).
const SEVERITY_COLOR: Record<string, string> = {
  info: "text-ink-500",
  low: "text-ink-300",
  medium: "text-signal-yellow",
  high: "text-signal-orange",
  critical: "text-signal-red",
  emergency: "text-signal-red",
};

const LIFECYCLE_ORDER = ["detected", "investigating", "mitigated", "recovering", "resolved", "closed"];

export function IncidentFeed({ incidents }: { incidents: Incident[] }) {
  const router = useRouter();
  const [pendingId, setPendingId] = useState<number | null>(null);

  async function advance(incident: Incident) {
    const idx = LIFECYCLE_ORDER.indexOf(incident.status);
    const next = LIFECYCLE_ORDER[Math.min(idx + 1, LIFECYCLE_ORDER.length - 1)];
    if (next === incident.status) return;
    setPendingId(incident.id);
    try {
      await fetch("/api/incident-update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_id: incident.id, status: next }),
      });
      router.refresh();
    } finally {
      setPendingId(null);
    }
  }

  const openCount = incidents.filter((i) => i.status !== "resolved" && i.status !== "closed").length;

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
        Incident Center {openCount > 0 ? `(${openCount} open)` : "(none open)"}
      </p>
      {incidents.length === 0 && <p className="text-xs text-ink-500">No incidents recorded — nothing critical has been detected.</p>}
      <div className="space-y-1.5">
        {incidents.map((i) => (
          <div key={i.id} className="flex items-center justify-between rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
            <div className="min-w-0">
              <p className="truncate">
                <span className={SEVERITY_COLOR[i.severity] ?? "text-ink-300"}>{i.severity.toUpperCase()}</span>{" "}
                <span className="text-ink-500">[{i.category}]</span> <span className="text-ink-100">{i.title}</span>
              </p>
              <p className="text-[10px] text-ink-500">
                {new Date(i.detected_at).toLocaleString()} · status: {i.status}
              </p>
            </div>
            {i.status !== "closed" && (
              <button
                onClick={() => advance(i)}
                disabled={pendingId === i.id}
                className="ml-3 shrink-0 rounded border border-base-600 px-2 py-1 text-[10px] uppercase text-ink-300 hover:bg-base-800 disabled:opacity-50"
              >
                {pendingId === i.id ? "…" : `→ ${LIFECYCLE_ORDER[LIFECYCLE_ORDER.indexOf(i.status) + 1]}`}
              </button>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
