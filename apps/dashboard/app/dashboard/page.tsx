import { cookies } from "next/headers";
import {
  getAssets,
  getHealth,
  getOpportunities,
  getPortfolio,
  getPositions,
  getRegimes,
  getSystemStatus,
  getTrades,
} from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { RiskBadge } from "@/components/RiskBadge";
import { RegimeBadge } from "@/components/RegimeBadge";
import { TierBadge } from "@/components/TierBadge";
import { LogoutButton } from "@/components/LogoutButton";

export const dynamic = "force-dynamic";

const eur = (n: number) =>
  new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(n);

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [health, status, portfolio, assets, positions, opportunities, regimes, trades] = await Promise.all([
    getHealth(),
    getSystemStatus(token),
    getPortfolio(),
    getAssets(),
    getPositions("open"),
    getOpportunities(10),
    getRegimes(),
    getTrades(8),
  ]);

  const systemOnline = health?.overall === "green";
  const dailyPnl = portfolio?.daily_pnl ?? 0;
  const regimeBySymbol = new Map((regimes ?? []).map((r) => [r.asset_symbol, r]));

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-8">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold uppercase tracking-widest text-ink-100">
            AI Quant System
          </h1>
          <p className="text-xs text-ink-500">OgrowNT — private paper trading desk</p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 text-xs ${
              systemOnline ? "text-signal-green" : "text-signal-red"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${systemOnline ? "bg-signal-green" : "bg-signal-red"}`}
            />
            SYSTEM: {systemOnline ? "ONLINE" : "DEGRADED"}
          </span>
          <LogoutButton />
        </div>
      </header>

      <section className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Paper Capital" value={portfolio ? eur(portfolio.cash) : "—"} />
        <StatCard label="Equity" value={portfolio ? eur(portfolio.equity) : "—"} />
        <StatCard
          label="P&L (today)"
          value={portfolio ? eur(dailyPnl) : "—"}
          tone={dailyPnl > 0 ? "positive" : dailyPnl < 0 ? "negative" : "default"}
        />
        <StatCard label="Max Drawdown" value={portfolio ? `${portfolio.drawdown_pct.toFixed(2)}%` : "—"} />
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[11px] uppercase tracking-wider text-ink-500">Risk State</p>
          <RiskBadge level={status?.safety_belt_level ?? portfolio?.safety_belt_level ?? "normal"} />
        </div>
        <p className="text-xs text-ink-500">
          Trading enabled: {status?.trading_enabled === false ? "no (kill switch)" : "yes"}
        </p>
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
          Top Opportunities {opportunities ? `(${opportunities.length})` : ""}
        </p>
        {opportunities && opportunities.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-ink-500">
                  <th className="pb-2 pr-3 font-normal">Asset</th>
                  <th className="pb-2 pr-3 font-normal">Strategy</th>
                  <th className="pb-2 pr-3 font-normal">Dir</th>
                  <th className="pb-2 pr-3 font-normal">Regime</th>
                  <th className="pb-2 pr-3 font-normal">R:R</th>
                  <th className="pb-2 pr-3 font-normal">Score</th>
                  <th className="pb-2 font-normal">Tier</th>
                </tr>
              </thead>
              <tbody>
                {opportunities.map((o) => (
                  <tr key={o.signal_id} className="border-t border-base-700/60 hover:bg-base-800">
                    <td className="py-1.5 pr-3 text-ink-100">{o.asset_symbol}</td>
                    <td className="py-1.5 pr-3 text-ink-300">{o.strategy_name}</td>
                    <td
                      className={`py-1.5 pr-3 font-medium uppercase ${
                        o.direction === "long" ? "text-signal-green" : "text-signal-red"
                      }`}
                    >
                      {o.direction}
                    </td>
                    <td className="py-1.5 pr-3">
                      <RegimeBadge regime={o.regime} />
                    </td>
                    <td className="py-1.5 pr-3 text-ink-300">{o.risk_reward.toFixed(2)}</td>
                    <td className="py-1.5 pr-3 text-ink-100">{o.final_score.toFixed(1)}</td>
                    <td className="py-1.5">
                      <TierBadge tier={o.tier} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-ink-500">
            No opportunities above the &quot;watch&quot; threshold right now — the system is
            observing, not forcing a trade (docs/blueprint/00-overview.md).
          </p>
        )}
      </section>

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-base-700 bg-base-900 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
            Market Data — Assets ({assets?.length ?? 0})
          </p>
          <div className="max-h-64 space-y-1 overflow-y-auto pr-1">
            {assets && assets.length > 0 ? (
              assets.map((a) => {
                const regime = regimeBySymbol.get(a.symbol);
                return (
                  <div
                    key={a.id}
                    className="flex items-center justify-between rounded px-2 py-1.5 text-xs hover:bg-base-800"
                  >
                    <span className="text-ink-100">{a.symbol}</span>
                    {regime ? <RegimeBadge regime={regime.regime} /> : <span className="text-ink-500">{a.asset_class}</span>}
                  </div>
                );
              })
            ) : (
              <p className="text-xs text-ink-500">DATA_UNAVAILABLE</p>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-base-700 bg-base-900 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
            Active Positions {positions ? `(${positions.length})` : ""}
          </p>
          {positions && positions.length > 0 ? (
            <div className="space-y-2">
              {positions.map((p) => (
                <div key={p.id} className="rounded border border-base-700 px-2 py-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-ink-100">
                      {p.asset_symbol}{" "}
                      <span className={p.direction === "long" ? "text-signal-green" : "text-signal-red"}>
                        {p.direction.toUpperCase()}
                      </span>
                    </span>
                    <span className={(p.unrealized_pnl ?? 0) >= 0 ? "text-signal-green" : "text-signal-red"}>
                      {p.unrealized_pnl !== null ? eur(p.unrealized_pnl) : "—"}
                    </span>
                  </div>
                  <div className="mt-1 flex justify-between text-ink-500">
                    <span>{p.strategy_code}</span>
                    <span>
                      entry {p.entry_price.toFixed(4)} · stop {p.current_stop.toFixed(4)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-ink-500">
              None right now — no signal has cleared the Risk Engine this cycle. That&apos;s the
              correct outcome when there&apos;s no clear edge (docs/blueprint/00-overview.md).
            </p>
          )}
        </div>
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
          Recent Trades {trades ? `(${trades.length})` : ""}
        </p>
        {trades && trades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-ink-500">
                  <th className="pb-2 pr-3 font-normal">Asset</th>
                  <th className="pb-2 pr-3 font-normal">Strategy</th>
                  <th className="pb-2 pr-3 font-normal">Dir</th>
                  <th className="pb-2 pr-3 font-normal">P&amp;L</th>
                  <th className="pb-2 pr-3 font-normal">R</th>
                  <th className="pb-2 font-normal">Outcome</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id} className="border-t border-base-700/60 hover:bg-base-800">
                    <td className="py-1.5 pr-3 text-ink-100">{t.asset_symbol}</td>
                    <td className="py-1.5 pr-3 text-ink-300">{t.strategy_code}</td>
                    <td
                      className={`py-1.5 pr-3 font-medium uppercase ${
                        t.direction === "long" ? "text-signal-green" : "text-signal-red"
                      }`}
                    >
                      {t.direction}
                    </td>
                    <td className={`py-1.5 pr-3 ${t.pnl >= 0 ? "text-signal-green" : "text-signal-red"}`}>
                      {eur(t.pnl)}
                    </td>
                    <td className="py-1.5 pr-3 text-ink-300">{t.r_multiple !== null ? t.r_multiple.toFixed(2) : "—"}</td>
                    <td className="py-1.5">
                      <span
                        className={
                          t.outcome === "win"
                            ? "text-signal-green"
                            : t.outcome === "loss"
                              ? "text-signal-red"
                              : "text-ink-300"
                        }
                      >
                        {t.outcome}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-ink-500">No closed trades yet.</p>
        )}
      </section>

      <section className="rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">System Health</p>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {health?.components.map((c) => (
            <div key={c.name} className="flex items-center gap-2 text-xs">
              <span
                className={`h-2 w-2 rounded-full ${
                  c.status === "green" ? "bg-signal-green" : "bg-signal-red"
                }`}
              />
              <span className="text-ink-300">{c.name.replace("_", " ")}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
