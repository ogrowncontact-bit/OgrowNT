import { cookies } from "next/headers";
import { getAssets, getHealth, getPortfolio, getPositions, getSystemStatus } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { RiskBadge } from "@/components/RiskBadge";
import { LogoutButton } from "@/components/LogoutButton";

export const dynamic = "force-dynamic";

const eur = (n: number) =>
  new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(n);

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [health, status, portfolio, assets, positions] = await Promise.all([
    getHealth(),
    getSystemStatus(token),
    getPortfolio(),
    getAssets(),
    getPositions(),
  ]);

  const systemOnline = health?.overall === "green";
  const pnl = portfolio ? portfolio.equity - portfolio.cash + 0 : 0; // no positions yet in Phase 1
  const dailyPnl = portfolio?.daily_pnl ?? 0;

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-8">
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

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-base-700 bg-base-900 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
            Market Data — Assets ({assets?.length ?? 0})
          </p>
          <div className="max-h-64 space-y-1 overflow-y-auto pr-1">
            {assets && assets.length > 0 ? (
              assets.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between rounded px-2 py-1.5 text-xs hover:bg-base-800"
                >
                  <span className="text-ink-100">{a.symbol}</span>
                  <span className="text-ink-500">{a.asset_class}</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-ink-500">DATA_UNAVAILABLE</p>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-base-700 bg-base-900 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Active Positions</p>
          {positions && positions.length > 0 ? (
            <ul className="text-xs text-ink-100">
              {positions.map((_, i) => (
                <li key={i}>position #{i}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">None</p>
          )}

          <p className="mb-3 mt-6 text-[11px] uppercase tracking-wider text-ink-500">Opportunities</p>
          <p className="text-xs text-ink-500">
            None yet — Strategy &amp; Scoring Engine arrive in Phase 2.
          </p>
        </div>
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
