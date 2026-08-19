"use client";

import { useEffect, useRef, useState } from "react";
import type { Asset, BacktestJob, FullLabReport, Strategy } from "@/lib/api";

// Strategy Lab — "PROMPT 7" §44's layout: config -> Backtest -> Walk Forward
// -> Monte Carlo -> Stress Test -> Robustness -> Final Score -> Decision.
// Only "1m" has backfilled OHLCV history in this deployment (same reason
// apps/dashboard/components/RunBacktestForm.tsx hardcodes it) -- offering
// other timeframes here would just produce a silent zero-trades run.
const TIMEFRAME = "1m";
const POLL_INTERVAL_MS = 2000;

const STATUS_COLOR: Record<string, string> = {
  ROBUST: "text-signal-green",
  PROMISING: "text-signal-green",
  VALIDATING: "text-signal-yellow",
  EXPERIMENTAL: "text-signal-yellow",
  DEGRADED: "text-signal-orange",
  REJECTED: "text-signal-red",
  QUARANTINED: "text-signal-red",
};

function defaultRange() {
  const end = new Date();
  const start = new Date(end.getTime() - 3 * 24 * 60 * 60 * 1000);
  const toLocalInput = (d: Date) => d.toISOString().slice(0, 16);
  return { start: toLocalInput(start), end: toLocalInput(end) };
}

function pct(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(digits)}%`;
}

function num(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

export function StrategyLab({ strategies, assets }: { strategies: Strategy[]; assets: Asset[] }) {
  const range = defaultRange();
  const [strategyId, setStrategyId] = useState(strategies[0]?.id ?? 0);
  const [assetId, setAssetId] = useState(assets[0]?.id ?? 0);
  const [startTs, setStartTs] = useState(range.start);
  const [endTs, setEndTs] = useState(range.end);
  const [capital, setCapital] = useState(10000);
  const [job, setJob] = useState<BacktestJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function handleRun(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setJob(null);
    const res = await fetch("/api/lab-job", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        strategy_id: strategyId, asset_id: assetId, timeframe: TIMEFRAME,
        start_ts: new Date(startTs).toISOString(), end_ts: new Date(endTs).toISOString(),
        initial_capital: capital, monte_carlo_simulations: 300,
      }),
    });
    const body = await res.json();
    if (!res.ok) {
      setError(body.detail ?? "Failed to start Strategy Lab run");
      return;
    }
    setJob(body as BacktestJob);

    pollRef.current = setInterval(async () => {
      const pollRes = await fetch(`/api/lab-job/${body.id}`);
      if (!pollRes.ok) return;
      const updated = (await pollRes.json()) as BacktestJob;
      setJob(updated);
      if (updated.status === "completed" || updated.status === "failed" || updated.status === "cancelled") {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, POLL_INTERVAL_MS);
  }

  if (strategies.length === 0 || assets.length === 0) {
    return <p className="text-xs text-ink-500">No strategies/assets available for the Strategy Lab.</p>;
  }

  const report = job?.status === "completed" ? (job.result as unknown as FullLabReport) : null;
  const running = job !== null && (job.status === "queued" || job.status === "running");

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Strategy Lab</p>

      <form onSubmit={handleRun} className="mb-4 flex flex-wrap items-end gap-3 border-b border-base-700/60 pb-4">
        <label className="flex flex-col gap-1 text-[11px] text-ink-500">
          Strategy
          <select value={strategyId} onChange={(e) => setStrategyId(Number(e.target.value))} className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100">
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-ink-500">
          Asset
          <select value={assetId} onChange={(e) => setAssetId(Number(e.target.value))} className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100">
            {assets.map((a) => (
              <option key={a.id} value={a.id}>{a.symbol}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-ink-500">
          Timeframe
          <span className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100">{TIMEFRAME}</span>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-ink-500">
          From
          <input type="datetime-local" value={startTs} onChange={(e) => setStartTs(e.target.value)} className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100" />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-ink-500">
          To
          <input type="datetime-local" value={endTs} onChange={(e) => setEndTs(e.target.value)} className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100" />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-ink-500">
          Capital (EUR)
          <input type="number" min={1} value={capital} onChange={(e) => setCapital(Number(e.target.value))} className="w-24 rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100" />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-ink-500">
          Risk Model
          <span className="rounded border border-base-600 bg-base-950 px-2 py-1 text-xs text-ink-100" title="config/risk_limits.yaml -- the same production risk limits used in paper trading">production (default)</span>
        </label>
        <button type="submit" disabled={running} className="rounded border border-signal-green/40 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-signal-green transition hover:bg-signal-green/10 disabled:opacity-50">
          {running ? `Running (${job?.status})…` : "Run full lab"}
        </button>
        {error && <p className="w-full text-xs text-signal-red">{error}</p>}
      </form>

      {job?.status === "failed" && <p className="text-xs text-signal-red">Run failed: {job.error}</p>}

      {report?.blocked && (
        <p className="text-xs text-signal-red">BACKTEST_BLOCKED: {report.reason}</p>
      )}

      {report && !report.blocked && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Net Return" value={pct(report.performance?.net_return as number | null)} />
            <Stat label="Win Rate" value={pct(report.performance?.win_rate as number | null)} />
            <Stat label="Expectancy" value={num(report.performance?.expectancy as number | null)} suffix="R" />
            <Stat label="Max Drawdown" value={report.risk?.max_drawdown != null ? `${num(report.risk.max_drawdown as number)}%` : "—"} />
          </div>

          <Section title="Walk Forward">
            {report.walk_forward ? (
              <p className="text-xs text-ink-300">
                {report.walk_forward.num_windows} window(s) — consistent:{" "}
                <span className={report.walk_forward.consistent ? "text-signal-green" : report.walk_forward.consistent === false ? "text-signal-red" : "text-ink-500"}>
                  {report.walk_forward.consistent === null ? "insufficient data" : String(report.walk_forward.consistent)}
                </span>
                . {report.walk_forward.reason}
              </p>
            ) : (
              <p className="text-xs text-ink-500">Not run.</p>
            )}
          </Section>

          <Section title="Monte Carlo">
            {report.monte_carlo ? (
              <p className="text-xs text-ink-300">
                {report.monte_carlo.num_simulations} simulations ({report.monte_carlo.method}) — probability of loss{" "}
                <span className="text-ink-100">{pct(report.monte_carlo.probability_of_loss)}</span>. Median final equity{" "}
                {num(report.monte_carlo.percentiles?.final_equity?.p50 ?? null, 0)}.
              </p>
            ) : (
              <p className="text-xs text-ink-500">Not run.</p>
            )}
          </Section>

          <Section title="Stress Tests">
            {report.stress_tests && report.stress_tests.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="text-ink-500">
                      <th className="pb-2 pr-3 font-normal">Scenario</th>
                      <th className="pb-2 pr-3 font-normal">Return Δ</th>
                      <th className="pb-2 pr-3 font-normal">Drawdown Δ</th>
                      <th className="pb-2 font-normal">Survived</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.stress_tests.map((s) => (
                      <tr key={s.scenario} className="border-t border-base-700/60">
                        <td className="py-1.5 pr-3 text-ink-100">{s.scenario.replace(/_/g, " ")}</td>
                        <td className="py-1.5 pr-3 text-ink-300">{s.return_delta !== null ? pct(s.return_delta) : "—"}</td>
                        <td className="py-1.5 pr-3 text-ink-300">{s.drawdown_delta !== null ? num(s.drawdown_delta) : "—"}</td>
                        <td className={`py-1.5 ${s.survived ? "text-signal-green" : s.survived === false ? "text-signal-red" : "text-ink-500"}`}>
                          {s.survived === null ? "n/a" : String(s.survived)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-ink-500">Not run.</p>
            )}
          </Section>

          <Section title="Robustness">
            {report.robustness ? (
              <div>
                <p className="mb-1 text-xs text-ink-100">Score: {num(report.robustness.score, 1)}/100</p>
                <div className="flex flex-wrap gap-2">
                  {report.robustness.components.map((c) => (
                    <span key={c.name} className="rounded border border-base-700 px-2 py-0.5 text-[10px] text-ink-300" title={c.evidence}>
                      {c.name.replace(/_/g, " ")}: {num(c.score, 1)}/{c.max_score}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-ink-500">Not run.</p>
            )}
          </Section>

          <Section title="Final Score / Decision">
            {report.final_assessment ? (
              <div className="flex flex-wrap items-center gap-3">
                <span className={`rounded border px-2 py-1 text-xs font-semibold uppercase tracking-wide ${STATUS_COLOR[report.final_assessment.status] ?? "text-ink-300"}`}>
                  {report.final_assessment.status}
                </span>
                <span className="text-xs text-ink-300">Quality score: {num(report.final_assessment.quality_score, 1)}/100</span>
                <span className="text-xs text-ink-300">Assessment: {report.final_assessment.assessment}</span>
              </div>
            ) : (
              <p className="text-xs text-ink-500">Not run.</p>
            )}
            <p className="mt-2 text-[10px] text-ink-500">
              This score reflects evidence gathered by the lab, not a probability of profit — see docs/backtest-lab.md.
            </p>
          </Section>
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, suffix }: { label: string; value: string; suffix?: string }) {
  return (
    <div className="rounded-lg border border-base-700 bg-base-900 p-3">
      <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">{label}</p>
      <p className="text-sm font-semibold text-ink-100">
        {value}
        {suffix && value !== "—" ? suffix : ""}
      </p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">{title}</p>
      {children}
    </div>
  );
}
