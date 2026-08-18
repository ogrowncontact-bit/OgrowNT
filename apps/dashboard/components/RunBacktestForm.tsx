"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Asset, BacktestSummary, Strategy } from "@/lib/api";

// Only "1m" has backfilled OHLCV history (apps/worker/history.py) -- exposing
// other timeframes here would just produce a silent zero-trades backtest,
// so the picker doesn't offer what the system can't actually run.
const TIMEFRAME = "1m";

function defaultRange() {
  const end = new Date();
  const start = new Date(end.getTime() - 3 * 24 * 60 * 60 * 1000);
  const toLocalInput = (d: Date) => d.toISOString().slice(0, 16);
  return { start: toLocalInput(start), end: toLocalInput(end) };
}

export function RunBacktestForm({ strategies, assets }: { strategies: Strategy[]; assets: Asset[] }) {
  const router = useRouter();
  const range = defaultRange();
  const [strategyId, setStrategyId] = useState(strategies[0]?.id ?? 0);
  const [assetId, setAssetId] = useState(assets[0]?.id ?? 0);
  const [startTs, setStartTs] = useState(range.start);
  const [endTs, setEndTs] = useState(range.end);
  const [capital, setCapital] = useState(10000);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setMessage(null);
    try {
      const res = await fetch("/api/run-backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy_id: strategyId,
          asset_id: assetId,
          timeframe: TIMEFRAME,
          start_ts: new Date(startTs).toISOString(),
          end_ts: new Date(endTs).toISOString(),
          initial_capital: capital,
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        setMessage({ tone: "error", text: body.detail ?? "Backtest failed" });
        return;
      }
      const result = body as BacktestSummary;
      setMessage({
        tone: "ok",
        text: `Run #${result.id}: ${result.num_trades} trades, net return ${
          result.net_return !== null ? `${(result.net_return * 100).toFixed(2)}%` : "—"
        }, win rate ${result.win_rate !== null ? `${Math.round(result.win_rate * 100)}%` : "—"}.`,
      });
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  if (strategies.length === 0 || assets.length === 0) {
    return <p className="text-xs text-ink-500">No strategies/assets available to backtest.</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="mb-4 flex flex-wrap items-end gap-3 border-b border-base-700/60 pb-4">
      <label className="flex flex-col gap-1 text-[11px] text-ink-500">
        Strategy
        <select
          value={strategyId}
          onChange={(e) => setStrategyId(Number(e.target.value))}
          className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100"
        >
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[11px] text-ink-500">
        Asset
        <select
          value={assetId}
          onChange={(e) => setAssetId(Number(e.target.value))}
          className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100"
        >
          {assets.map((a) => (
            <option key={a.id} value={a.id}>
              {a.symbol}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[11px] text-ink-500">
        From
        <input
          type="datetime-local"
          value={startTs}
          onChange={(e) => setStartTs(e.target.value)}
          className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100"
        />
      </label>
      <label className="flex flex-col gap-1 text-[11px] text-ink-500">
        To
        <input
          type="datetime-local"
          value={endTs}
          onChange={(e) => setEndTs(e.target.value)}
          className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100"
        />
      </label>
      <label className="flex flex-col gap-1 text-[11px] text-ink-500">
        Capital (EUR)
        <input
          type="number"
          min={1}
          value={capital}
          onChange={(e) => setCapital(Number(e.target.value))}
          className="w-24 rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100"
        />
      </label>
      <button
        type="submit"
        disabled={pending}
        className="rounded border border-signal-green/40 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-signal-green transition hover:bg-signal-green/10 disabled:opacity-50"
      >
        {pending ? "Running…" : "Run backtest"}
      </button>
      {message && (
        <p className={`w-full text-xs ${message.tone === "ok" ? "text-signal-green" : "text-signal-red"}`}>
          {message.text}
        </p>
      )}
    </form>
  );
}
