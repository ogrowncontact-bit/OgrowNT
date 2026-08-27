import type { MarketAssetOverview, MarketOverview } from "@/lib/api";

// Data Center — "PROMPT 14" §56-58. Reuses the exact same per-asset
// data_quality_score/data_quality_status/last_update fields
// packages/data/quality.py already computes and GET /api/market/overview
// already returns (Prompt 11) — no second data-quality engine, just a
// dedicated page for what was previously only visible inline on
// /dashboard's "Market Data" section.
function ageSeconds(lastUpdate: string | null): number | null {
  if (!lastUpdate) return null;
  return Math.max(0, (Date.now() - new Date(lastUpdate).getTime()) / 1000);
}

const QUALITY_COLOR: Record<string, string> = {
  GOOD: "text-signal-green",
  DEGRADED: "text-signal-yellow",
  DATA_UNSAFE: "text-signal-red",
};

function freshnessLabel(seconds: number | null): { label: string; color: string } {
  if (seconds === null) return { label: "NO DATA", color: "text-signal-red" };
  if (seconds < 120) return { label: `${seconds.toFixed(0)}s`, color: "text-signal-green" };
  if (seconds < 900) return { label: `${(seconds / 60).toFixed(1)}m`, color: "text-signal-yellow" };
  return { label: `${(seconds / 60).toFixed(0)}m`, color: "text-signal-red" };
}

export function DataFreshnessPanel({ overview }: { overview: MarketOverview | null }) {
  const assets: MarketAssetOverview[] = overview?.assets ?? [];
  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">Data Center</p>
        <span className="text-[10px] text-ink-500">
          provider: {overview?.data_source.provider ?? "unknown"} ({overview?.data_source.is_live ? "live" : "mock"})
        </span>
      </div>
      {assets.length === 0 ? (
        <p className="text-xs text-ink-500">No market data sources configured.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wide text-ink-500">
                <th className="pb-2 pr-3 font-normal">Asset</th>
                <th className="pb-2 pr-3 font-normal">Last update</th>
                <th className="pb-2 pr-3 font-normal">Freshness</th>
                <th className="pb-2 font-normal">Quality</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => {
                const seconds = ageSeconds(a.last_update);
                const fresh = freshnessLabel(seconds);
                return (
                  <tr key={a.symbol} className="border-t border-base-700/60">
                    <td className="py-1.5 pr-3 text-ink-100">{a.symbol}</td>
                    <td className="py-1.5 pr-3 text-ink-500">{a.last_update ? new Date(a.last_update).toLocaleTimeString() : "never"}</td>
                    <td className={`py-1.5 pr-3 ${fresh.color}`}>{fresh.label}</td>
                    <td className={`py-1.5 ${QUALITY_COLOR[a.data_quality_status ?? ""] ?? "text-ink-500"}`}>
                      {a.data_quality_status ?? "—"} {a.data_quality_score != null ? `(${a.data_quality_score.toFixed(0)})` : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
