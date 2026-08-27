import { cookies } from "next/headers";
import { getAnalyticsOverview, getDashboardPortfolio } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { EquitySparkline } from "@/components/EquitySparkline";
import { ClosePositionButton } from "@/components/ClosePositionButton";

export const dynamic = "force-dynamic";

const usd = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

export default async function PortfolioPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [data, analytics] = await Promise.all([getDashboardPortfolio(token), getAnalyticsOverview(token)]);

  return (
    <div>
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Equity" value={data ? usd(data.portfolio.equity) : "—"} />
        <StatCard label="Cash" value={data ? usd(data.portfolio.cash) : "—"} />
        <StatCard
          label="Daily P&L"
          value={data ? usd(data.portfolio.daily_pnl) : "—"}
          tone={data && data.portfolio.daily_pnl >= 0 ? "positive" : "negative"}
        />
        <StatCard label="Exposure" value={data ? `${data.portfolio.exposure_pct.toFixed(1)}%` : "—"} />
        <StatCard label="Weekly P&L" value={data ? usd(data.portfolio.weekly_pnl) : "—"} tone={data && data.portfolio.weekly_pnl >= 0 ? "positive" : "negative"} />
        <StatCard label="Monthly P&L" value={data ? usd(data.portfolio.monthly_pnl) : "—"} tone={data && data.portfolio.monthly_pnl >= 0 ? "positive" : "negative"} />
        <StatCard label="Drawdown" value={data ? `${data.portfolio.drawdown_pct.toFixed(1)}%` : "—"} tone="negative" />
        <StatCard label="Safety Belt" value={data?.portfolio.safety_belt_level ?? "—"} />
      </div>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Equity Curve</p>
        <EquitySparkline points={analytics?.equity_curve ?? []} />
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
          Active Positions {data ? `(${data.positions.length})` : ""}
        </p>
        {data && data.positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-ink-500">
                  <th className="pb-2 pr-3 font-normal">Asset</th>
                  <th className="pb-2 pr-3 font-normal">Side</th>
                  <th className="pb-2 pr-3 font-normal">Entry</th>
                  <th className="pb-2 pr-3 font-normal">Size</th>
                  <th className="pb-2 pr-3 font-normal">Unrealized</th>
                  <th className="pb-2 font-normal"></th>
                </tr>
              </thead>
              <tbody>
                {data.positions.map((p) => (
                  <tr key={p.id} className="border-t border-base-700/60">
                    <td className="py-1.5 pr-3 text-ink-100">{p.asset_symbol}</td>
                    <td className={`py-1.5 pr-3 uppercase ${p.direction === "long" ? "text-signal-green" : "text-signal-red"}`}>
                      {p.direction}
                    </td>
                    <td className="py-1.5 pr-3 text-ink-300">{p.entry_price.toFixed(4)}</td>
                    <td className="py-1.5 pr-3 text-ink-300">{p.size.toFixed(4)}</td>
                    <td className={`py-1.5 pr-3 ${(p.unrealized_pnl ?? 0) >= 0 ? "text-signal-green" : "text-signal-red"}`}>
                      {p.unrealized_pnl != null ? usd(p.unrealized_pnl) : "—"}
                    </td>
                    <td className="py-1.5">
                      <ClosePositionButton positionId={p.id} assetSymbol={p.asset_symbol} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-ink-500">No open positions.</p>
        )}
      </section>

      <section className="rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Recent Trades</p>
        {data && data.recent_trades.length > 0 ? (
          <div className="space-y-1">
            {data.recent_trades.map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
                <span>
                  <span className="text-ink-100">{t.asset_symbol}</span> <span className="text-ink-500">{t.strategy_code}</span>
                </span>
                <span className={t.pnl >= 0 ? "text-signal-green" : "text-signal-red"}>{usd(t.pnl)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No trades closed yet.</p>
        )}
      </section>
    </div>
  );
}
