"use client";

import { useCallback, useRef, useSyncExternalStore } from "react";
import Link from "next/link";
import { useEventStream } from "@/lib/useEventStream";
import type { MarketSessionEntry } from "@/lib/api";

// "PROMPT 14" §5-7: SYSTEM/MARKETS/RISK/EXECUTION/LIVE TRADING status +
// heartbeat + clock, in one always-visible bar above every Command Center
// page (apps/dashboard/app/command-center/layout.tsx). Initial values come
// from the layout's own server-side fetch (so the bar is never blank on
// first paint); the "system" WebSocket channel then refreshes
// trading_enabled/trading_paused/safety_belt_level live from each tick's
// heartbeat event without a page reload — the connection indicator itself
// (LIVE / RECONNECTING / OFFLINE) is never faked (§102).

export type GlobalStatusBarProps = {
  tradingEnabled: boolean | null;
  tradingPaused: boolean | null;
  safetyBeltLevel: string | null;
  tradingMode: string | null;
  healthScore: number | null;
  readinessState: string | null;
  sessions: MarketSessionEntry[];
};

function marketsLabel(sessions: MarketSessionEntry[]): string {
  if (sessions.length === 0) return "UNKNOWN";
  const openCount = sessions.filter((s) => s.state === "open").length;
  if (openCount === sessions.length) return "OPEN";
  if (openCount === 0) return "CLOSED";
  return "MIXED";
}

function riskLabel(safetyBeltLevel: string | null): string {
  if (!safetyBeltLevel) return "UNKNOWN";
  if (safetyBeltLevel === "kill_switch") return "CRITICAL";
  return safetyBeltLevel.toUpperCase();
}

const RISK_COLOR: Record<string, string> = {
  NORMAL: "text-signal-green",
  CAUTION: "text-signal-yellow",
  DEFENSIVE: "text-signal-orange",
  EMERGENCY: "text-signal-red",
  CRITICAL: "text-signal-red",
  UNKNOWN: "text-ink-500",
};

const CONN_COLOR: Record<string, string> = {
  open: "text-signal-green",
  connecting: "text-signal-yellow",
  closed: "text-signal-red",
  error: "text-signal-red",
};
const CONN_LABEL: Record<string, string> = {
  open: "LIVE",
  connecting: "CONNECTING",
  closed: "RECONNECTING",
  error: "OFFLINE",
};

// useSyncExternalStore rather than useState+useEffect: the clock's "current
// time" is genuinely external state (the system clock via setInterval), and
// this avoids both the synchronous-setState-in-effect anti-pattern and a
// server/client hydration mismatch (getServerSnapshot returns null, so SSR
// output never embeds a server-side timestamp the client would disagree
// with on hydration). getSnapshot must return a CACHED reference — a fresh
// `new Date()` on every call reads as "always changed" and free-spins React
// into "Maximum update depth exceeded" (caught by the live browser
// verification pass for this phase) — so the ticking value lives in a ref,
// updated only once a second by the subscription itself.
function useClock(): Date | null {
  const timeRef = useRef<Date | null>(null);

  const subscribe = useCallback((callback: () => void) => {
    const id = setInterval(() => {
      timeRef.current = new Date();
      callback();
    }, 1000);
    return () => clearInterval(id);
  }, []);
  const getSnapshot = useCallback(() => {
    if (timeRef.current === null) timeRef.current = new Date();
    return timeRef.current;
  }, []);
  const getServerSnapshot = useCallback(() => null, []);

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function GlobalStatusBar(props: GlobalStatusBarProps) {
  const { status, lastEvent, stale } = useEventStream("system");
  const now = useClock();

  const payload = (lastEvent?.payload ?? {}) as Record<string, unknown>;
  const tradingEnabled = (payload.trading_enabled as boolean | undefined) ?? props.tradingEnabled;
  const tradingPaused = (payload.trading_paused as boolean | undefined) ?? props.tradingPaused;
  const safetyBeltLevel = (payload.safety_belt_level as string | undefined) ?? props.safetyBeltLevel;
  const tradingMode = (payload.trading_mode as string | undefined) ?? props.tradingMode;

  const systemLabel = tradingEnabled === false ? "OFFLINE" : tradingPaused ? "DEGRADED" : "ONLINE";
  const systemColor = tradingEnabled === false ? "text-signal-red" : tradingPaused ? "text-signal-yellow" : "text-signal-green";
  const risk = riskLabel(safetyBeltLevel ?? null);

  return (
    <div className="flex h-11 shrink-0 items-center justify-between border-b border-base-700 bg-base-950 px-4 text-[11px]">
      <div className="flex items-center gap-4">
        <Link href="/command-center" className="font-semibold text-ink-100">
          COMMAND CENTER
        </Link>
        <span className="text-ink-500">
          SYSTEM: <span className={systemColor}>{systemLabel}</span>
        </span>
        <span className="text-ink-500">
          MARKETS: <span className="text-ink-100">{marketsLabel(props.sessions)}</span>
        </span>
        <span className="text-ink-500">
          RISK: <span className={RISK_COLOR[risk] ?? "text-ink-500"}>{risk}</span>
        </span>
        <span className="text-ink-500">
          MODE: <span className="text-ink-100">{(tradingMode ?? "paper").toUpperCase()}</span>
        </span>
        <span className="text-signal-green">LIVE TRADING: DISABLED</span>
        {props.healthScore != null && (
          <span className="text-ink-500">
            HEALTH: <span className="text-ink-100">{props.healthScore.toFixed(0)}</span>
            {props.readinessState ? ` (${props.readinessState.replace("_", " ").toUpperCase()})` : ""}
          </span>
        )}
      </div>
      <div className="flex items-center gap-4">
        <span className={stale ? "text-signal-yellow" : (CONN_COLOR[status] ?? "text-ink-500")}>
          {stale ? "STALE DATA" : (CONN_LABEL[status] ?? status.toUpperCase())}
        </span>
        <span className="text-ink-500">
          UTC {now ? now.toISOString().slice(11, 19) : "--:--:--"}
        </span>
      </div>
    </div>
  );
}
