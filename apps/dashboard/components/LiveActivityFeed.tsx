import type { TradingEvent } from "@/lib/api";

// "PROMPT 8" §59 — "# AI ACTIVITY": a human-readable line per TradingEvent,
// not the raw JSON payload. Falls back to the event_type itself for
// anything this mapping doesn't recognize yet, rather than hiding it.
function describe(event: TradingEvent): string {
  const p = event.payload ?? {};
  switch (event.event_type) {
    case "order_submitted":
      return `Order submitted (${p.purpose ?? "?"}, ${p.side ?? "?"} ${p.qty ?? "?"})`;
    case "order_filled":
      return `Order filled at ${typeof p.filled_price === "number" ? p.filled_price.toFixed(4) : p.filled_price}`;
    case "order_rejected":
      return `Order rejected — ${p.status ?? "unknown"}`;
    case "position_opened":
      return `Opened ${p.direction ?? ""} ${p.asset ?? ""} @ ${typeof p.entry_price === "number" ? p.entry_price.toFixed(4) : p.entry_price}`;
    case "position_closed":
      return `Closed ${p.asset ?? ""} (${p.exit_reason ?? "?"}) — ${p.outcome ?? "?"}, pnl ${p.pnl ?? "?"}`;
    case "risk_blocked":
      return `Risk blocked (${p.layer ?? "risk_engine"}) — ${p.reason ?? "?"}`;
    case "no_trade":
      return `No trade — ${p.asset ?? ""} ${p.strategy ?? ""} filtered at ${p.stage ?? "?"} (tier ${p.tier ?? "?"})`;
    case "trading_paused":
      return `Trading paused — ${p.reason ?? "?"}`;
    case "trading_resumed":
      return "Trading resumed";
    case "kill_switch_triggered":
      return "Kill switch triggered";
    case "kill_switch_released":
      return "Kill switch released";
    case "reconciliation_mismatch":
      return `Reconciliation mismatch — ${Array.isArray(p.violations) ? p.violations.length : "?"} violation(s)`;
    case "portfolio_emergency_action":
      return `Position risk action: ${p.action ?? "?"} (${p.trigger ?? "?"}) — ${p.reason ?? ""}`;
    case "loss_streak_detected":
      return `Loss streak detected — ${p.consecutive_losses ?? "?"} in a row`;
    case "worker_restarted":
      return `Worker restarted (#${p.restart_count ?? "?"})`;
    case "crash_loop_protection_triggered":
      return `Crash-loop protection triggered — trading paused (#${p.restart_count ?? "?"} restarts)`;
    default:
      return event.event_type.replace(/_/g, " ");
  }
}

function hhmm(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const SEVERITY_TONE: Record<string, string> = {
  risk_blocked: "text-signal-yellow",
  no_trade: "text-ink-500",
  order_rejected: "text-signal-red",
  trading_paused: "text-signal-yellow",
  kill_switch_triggered: "text-signal-red",
  reconciliation_mismatch: "text-signal-red",
  crash_loop_protection_triggered: "text-signal-red",
  position_opened: "text-signal-green",
};

export function LiveActivityFeed({ events }: { events: TradingEvent[] }) {
  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500"># AI ACTIVITY {events.length ? `(${events.length})` : ""}</p>
      {events.length > 0 ? (
        <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
          {events.map((e) => (
            <div key={e.id} className="flex items-start gap-3 text-xs">
              <span className="w-12 shrink-0 text-ink-500">{hhmm(e.ts)}</span>
              <span className={SEVERITY_TONE[e.event_type] ?? "text-ink-300"}>{describe(e)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-ink-500">No activity recorded yet.</p>
      )}
    </section>
  );
}
