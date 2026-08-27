import { cookies } from "next/headers";
import {
  getDynamicWatchlist,
  getMarketAnomalies,
  getMarketOverview,
  getMarketUniverse,
  getOpportunityClusters,
  getGlobalMarketSessions,
  getVolatilityEvents,
} from "@/lib/api";
import { GlobalMarketCommandCenter } from "@/components/GlobalMarketCommandCenter";
import { RegimeBadge } from "@/components/RegimeBadge";

export const dynamic = "force-dynamic";

export default async function MarketsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [universe, volatilityEvents, anomalies, watchlist, clusters, sessions, overview] = await Promise.all([
    getMarketUniverse(token),
    getVolatilityEvents(token),
    getMarketAnomalies(token),
    getDynamicWatchlist(token),
    getOpportunityClusters(token),
    getGlobalMarketSessions(token),
    getMarketOverview(token),
  ]);

  return (
    <div>
      <GlobalMarketCommandCenter
        universe={universe}
        volatilityEvents={volatilityEvents}
        anomalies={anomalies}
        watchlist={watchlist}
        clusters={clusters}
        sessions={sessions}
      />
      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Market Overview</p>
        {overview && overview.assets.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-ink-500">
                  <th className="pb-2 pr-3 font-normal">Asset</th>
                  <th className="pb-2 pr-3 font-normal">Class</th>
                  <th className="pb-2 pr-3 font-normal">Price</th>
                  <th className="pb-2 pr-3 font-normal">Change</th>
                  <th className="pb-2 font-normal">Trend</th>
                </tr>
              </thead>
              <tbody>
                {overview.assets.map((a) => (
                  <tr key={a.symbol} className="border-t border-base-700/60">
                    <td className="py-1.5 pr-3 text-ink-100">{a.symbol}</td>
                    <td className="py-1.5 pr-3 text-ink-500">{a.asset_class}</td>
                    <td className="py-1.5 pr-3 text-ink-300">{a.price?.toFixed(2) ?? "—"}</td>
                    <td className={`py-1.5 pr-3 ${a.pct_change != null && a.pct_change < 0 ? "text-signal-red" : "text-signal-green"}`}>
                      {a.pct_change != null ? `${a.pct_change >= 0 ? "+" : ""}${a.pct_change.toFixed(2)}%` : "—"}
                    </td>
                    <td className="py-1.5">{a.trend && <RegimeBadge regime={a.trend} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-ink-500">No market data yet.</p>
        )}
      </section>
    </div>
  );
}
