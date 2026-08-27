import { cookies } from "next/headers";
import {
  getDashboardAgents,
  getDashboardEvents,
  getDashboardMarketPulse,
  getDashboardOpportunities,
  getDashboardOverview,
} from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { RegimeBadge } from "@/components/RegimeBadge";
import { OpportunityRadar } from "@/components/OpportunityRadar";
import { ChiefDecisionPanel } from "@/components/ChiefDecisionPanel";
import { LiveActivityFeed } from "@/components/LiveActivityFeed";
import { CommandBar } from "@/components/CommandBar";

export const dynamic = "force-dynamic";

const usd = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

export default async function CommandCenterHomePage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [overview, marketPulse, opportunities, agents, events] = await Promise.all([
    getDashboardOverview(token),
    getDashboardMarketPulse(token),
    getDashboardOpportunities(token),
    getDashboardAgents(token),
    getDashboardEvents(token),
  ]);

  return (
    <div>
      <CommandBar />

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Equity" value={overview ? usd(overview.portfolio.equity) : "—"} />
        <StatCard
          label="Daily P&L"
          value={overview ? usd(overview.portfolio.daily_pnl) : "—"}
          tone={overview && overview.portfolio.daily_pnl >= 0 ? "positive" : "negative"}
        />
        <StatCard label="Open Positions" value={overview ? String(overview.positions_open) : "—"} />
        <StatCard
          label="Active Incidents"
          value={overview ? String(overview.active_incidents) : "—"}
          tone={overview && overview.active_incidents > 0 ? "negative" : "positive"}
        />
      </div>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Global Market Pulse</p>
        {marketPulse && marketPulse.overview.assets.length > 0 ? (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {marketPulse.overview.assets.slice(0, 8).map((a) => (
              <div key={a.symbol} className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-ink-100">{a.symbol}</span>
                  {a.trend && <RegimeBadge regime={a.trend} />}
                </div>
                <p className={a.pct_change != null && a.pct_change < 0 ? "text-signal-red" : "text-signal-green"}>
                  {a.price != null ? a.price.toFixed(2) : "—"}
                  {a.pct_change != null ? ` (${a.pct_change >= 0 ? "+" : ""}${a.pct_change.toFixed(2)}%)` : ""}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No market data yet.</p>
        )}
        <p className="mt-3 text-[10px] text-ink-500">
          {marketPulse?.sessions.sessions.filter((s) => s.state === "open").length ?? 0} of{" "}
          {marketPulse?.sessions.sessions.length ?? 0} sessions open
        </p>
      </section>

      <OpportunityRadar opportunities={opportunities?.opportunities.slice(0, 10) ?? []} />
      <ChiefDecisionPanel decisions={agents?.recent_decisions ?? []} />
      <LiveActivityFeed events={events?.activity_feed.slice(0, 15) ?? []} />
    </div>
  );
}
