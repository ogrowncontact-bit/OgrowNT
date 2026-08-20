import type {
  AnomalyEntry,
  AssetUniverseEntry,
  GlobalMarketSnapshot,
  OpportunityClusterEntry,
  VolatilityEventEntry,
  WatchlistEntryItem,
} from "@/lib/api";

// Global Market Command Center — "PROMPT 11" §80-84: the market
// intelligence pipeline's own dashboard surface. Deliberately does NOT
// duplicate sections that already exist elsewhere in this dashboard (Top
// Opportunities, Market Regimes, News, Macro Events, Correlation Map,
// Portfolio Exposure, Risk all have their own panels already) — this one
// covers only what's genuinely new: the asset universe's health/liquidity
// standing, the Dynamic Watchlist, recent anomalies, volatility regime
// transitions, correlated-opportunity clusters, and the global session
// clock. Read-only: nothing here can execute a trade — the scanner NEVER
// does (§95).

const STATUS_COLOR: Record<string, string> = {
  active: "text-signal-green",
  inactive: "text-ink-500",
  suspended: "text-ink-500",
  data_unavailable: "text-signal-yellow",
  low_liquidity: "text-signal-yellow",
  quarantined: "text-signal-red",
};

const SESSION_STATE_COLOR: Record<string, string> = {
  open: "text-signal-green",
  "24h": "text-signal-green",
  pre_market: "text-signal-yellow",
  post_market: "text-signal-yellow",
  transition: "text-signal-yellow",
  closed: "text-ink-500",
  unknown: "text-ink-500",
};

const VOLATILITY_EVENT_COLOR: Record<string, string> = {
  spike: "text-signal-red",
  expansion: "text-signal-yellow",
  compression: "text-ink-500",
  collapse: "text-signal-green",
};

function anomalyScoreColor(score: number): string {
  if (score >= 80) return "text-signal-red";
  if (score >= 50) return "text-signal-yellow";
  return "text-ink-500";
}

function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function GlobalMarketCommandCenter({
  universe,
  volatilityEvents,
  anomalies,
  watchlist,
  clusters,
  sessions,
}: {
  universe: AssetUniverseEntry[] | null;
  volatilityEvents: VolatilityEventEntry[] | null;
  anomalies: AnomalyEntry[] | null;
  watchlist: WatchlistEntryItem[] | null;
  clusters: OpportunityClusterEntry[] | null;
  sessions: GlobalMarketSnapshot | null;
}) {
  const symbolById = new Map((universe ?? []).map((a) => [a.id, a.symbol]));
  const symbolFor = (assetId: number) => symbolById.get(assetId) ?? `asset #${assetId}`;

  const statusCounts = (universe ?? []).reduce<Record<string, number>>((acc, a) => {
    acc[a.status] = (acc[a.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">Global Market Command Center</p>
        <span className="text-xs text-ink-500">
          {universe?.length ?? 0} assets · {watchlist?.length ?? 0} watchlisted · {anomalies?.length ?? 0} recent anomalies
        </span>
      </div>
      <p className="mb-4 text-[10px] text-ink-500">
        Market information, opportunities and alerts only — the scanner never executes a trade. An anomaly means
        INVESTIGATE, not TRADE; a cluster is evidence of shared exposure, not a causal claim between assets.
      </p>

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Global Sessions</p>
      {sessions ? (
        <div className="mb-4">
          <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
            {sessions.sessions.map((s) => (
              <div key={s.session} className="rounded-lg border border-base-700 bg-base-900 p-2">
                <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">{s.session.replace("_", " ")}</p>
                <p className={`text-xs uppercase ${SESSION_STATE_COLOR[s.state] ?? "text-ink-500"}`}>{s.state}</p>
                <p className="mt-1 text-[10px] text-ink-500">{s.local_time}</p>
              </div>
            ))}
          </div>
          {sessions.active_overlaps.length > 0 && (
            <p className="mt-2 text-xs text-ink-300">
              Active overlaps: {sessions.active_overlaps.map((pair) => pair.join(" / ")).join(", ")}
            </p>
          )}
        </div>
      ) : (
        <p className="mb-4 text-xs text-ink-500">Session clock unavailable.</p>
      )}

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Asset Universe</p>
      {universe && universe.length > 0 ? (
        <div className="mb-4">
          <div className="mb-2 flex flex-wrap gap-2 text-[10px] text-ink-500">
            {Object.entries(statusCounts).map(([s, count]) => (
              <span key={s} className={STATUS_COLOR[s] ?? "text-ink-500"}>
                {s}: {count}
              </span>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-ink-500">
                  <th className="pb-2 pr-3 font-normal">Symbol</th>
                  <th className="pb-2 pr-3 font-normal">Class</th>
                  <th className="pb-2 pr-3 font-normal">Status</th>
                  <th className="pb-2 pr-3 font-normal">Liquidity</th>
                  <th className="pb-2 font-normal">Data Quality</th>
                </tr>
              </thead>
              <tbody>
                {universe.slice(0, 25).map((a) => (
                  <tr key={a.id} className="border-t border-base-700/60">
                    <td className="py-1.5 pr-3 text-ink-100">{a.symbol}</td>
                    <td className="py-1.5 pr-3 text-ink-500">{a.asset_class}</td>
                    <td className={`py-1.5 pr-3 uppercase ${STATUS_COLOR[a.status] ?? "text-ink-500"}`}>{a.status}</td>
                    <td className="py-1.5 pr-3 text-ink-300">{a.liquidity_score?.toFixed(0) ?? "—"}</td>
                    <td className="py-1.5 text-ink-300">{a.data_quality_score?.toFixed(0) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="mb-4 text-xs text-ink-500">Universe not yet evaluated — no assets recorded.</p>
      )}

      <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">
            Dynamic Watchlist {watchlist ? `(${watchlist.length})` : ""}
          </p>
          {watchlist && watchlist.length > 0 ? (
            <ul className="space-y-1">
              {watchlist.slice(0, 10).map((w) => (
                <li key={w.id} className="text-xs text-ink-300">
                  {symbolFor(w.asset_id)} — {w.reason} · {timeAgo(w.updated_at)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">Nothing currently watchlisted.</p>
          )}
        </div>

        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">
            Opportunity Clusters {clusters ? `(${clusters.length})` : ""}
          </p>
          {clusters && clusters.length > 0 ? (
            <ul className="space-y-1">
              {clusters.slice(0, 10).map((c) => (
                <li key={c.id} className="text-xs text-ink-300">
                  {c.direction} · {c.asset_ids.map((id) => symbolFor(id)).join(", ")} — corr{" "}
                  {(c.avg_correlation * 100).toFixed(0)}%, penalty {(c.ranking_penalty * 100).toFixed(0)}%
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">No correlated-exposure clusters detected right now.</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">
            Recent Anomalies {anomalies ? `(${anomalies.length})` : ""}
          </p>
          {anomalies && anomalies.length > 0 ? (
            <ul className="space-y-1">
              {anomalies.slice(0, 10).map((a) => (
                <li key={a.id} className={`text-xs ${anomalyScoreColor(a.score)}`}>
                  {symbolFor(a.asset_id)} — {a.anomaly_type} (score {a.score.toFixed(0)}) · {timeAgo(a.ts)}
                  {a.reviewed ? " · reviewed" : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">No anomalies detected recently.</p>
          )}
        </div>

        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">
            Volatility Events {volatilityEvents ? `(${volatilityEvents.length})` : ""}
          </p>
          {volatilityEvents && volatilityEvents.length > 0 ? (
            <ul className="space-y-1">
              {volatilityEvents.slice(0, 10).map((v) => (
                <li key={v.id} className={`text-xs ${VOLATILITY_EVENT_COLOR[v.event_type] ?? "text-ink-300"}`}>
                  {symbolFor(v.asset_id)} — {v.event_type} → {v.regime} (p{v.percentile.toFixed(0)}) · {timeAgo(v.ts)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">No volatility regime transitions recorded recently.</p>
          )}
        </div>
      </div>
    </section>
  );
}
