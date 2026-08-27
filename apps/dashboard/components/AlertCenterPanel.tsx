import type { SystemAlert } from "@/lib/api";

// Alert Center — "PROMPT 14" §63-65. §65's deduplication is enforced
// upstream: packages/notifications and apps/worker's own alert-raising call
// sites already collapse repeated conditions into one Alert row rather than
// firing on every tick (e.g. apps/worker/supervisor.py's
// CONSECUTIVE_FAILURE_ALERT_THRESHOLD fires exactly once per failure
// streak) — this panel just renders what already arrived, grouped by
// category for the "100 alerts for the same problem" scenario §65 warns
// against never actually reaching the dashboard in the first place.
const SEVERITY_COLOR: Record<string, string> = {
  info: "text-ink-500",
  warning: "text-signal-yellow",
  critical: "text-signal-red",
};

export function AlertCenterPanel({ alerts }: { alerts: SystemAlert[] }) {
  const byCategory = new Map<string, SystemAlert[]>();
  for (const alert of alerts) {
    const list = byCategory.get(alert.category) ?? [];
    list.push(alert);
    byCategory.set(alert.category, list);
  }

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
        Alert Center {alerts.length ? `(${alerts.length})` : ""}
      </p>
      {alerts.length === 0 ? (
        <p className="text-xs text-ink-500">No alerts.</p>
      ) : (
        <div className="space-y-3">
          {[...byCategory.entries()].map(([category, items]) => (
            <div key={category}>
              <p className="mb-1 text-[10px] uppercase tracking-wide text-ink-500">
                {category} ({items.length})
              </p>
              <div className="space-y-1">
                {items.map((a) => (
                  <div key={a.id} className="flex items-start justify-between rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
                    <span>
                      <span className={SEVERITY_COLOR[a.severity] ?? "text-ink-300"}>{a.severity.toUpperCase()}</span>{" "}
                      <span className="text-ink-100">{a.message}</span>
                    </span>
                    <span className="ml-3 shrink-0 text-[10px] text-ink-500">{new Date(a.ts).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
