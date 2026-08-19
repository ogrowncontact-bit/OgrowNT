import type { MacroEvent, NewsEvent, NewsRisk } from "@/lib/api";

// News Intelligence Center — Prompt 6 §33/44: Latest Events, Macro Events,
// Sentiment, Event Risk, News Momentum, Source Quality, Important Alerts
// (the last of those already surfaces in the dashboard's own Alerts panel,
// filed under category "news" — not duplicated here).

const SENTIMENT_COLOR: Record<string, string> = {
  very_bullish: "text-signal-green",
  bullish: "text-signal-green",
  neutral: "text-ink-500",
  bearish: "text-signal-red",
  very_bearish: "text-signal-red",
  unknown: "text-ink-500",
};

const IMPORTANCE_COLOR: Record<string, string> = {
  low: "text-ink-500",
  medium: "text-signal-yellow",
  high: "text-signal-orange",
  critical: "text-signal-red",
};

const RISK_LEVEL_COLOR: Record<string, string> = {
  normal: "bg-signal-green/15 text-signal-green border-signal-green/40",
  elevated: "bg-signal-yellow/15 text-signal-yellow border-signal-yellow/40",
  high: "bg-signal-orange/15 text-signal-orange border-signal-orange/40",
  critical: "bg-signal-red/15 text-signal-red border-signal-red/40",
};

function timeRelative(iso: string): string {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const abs = Math.abs(seconds);
  const unit = abs < 3600 ? [Math.round(abs / 60), "min"] : abs < 86400 ? [Math.round(abs / 3600), "h"] : [Math.round(abs / 86400), "d"];
  const label = `${unit[0]}${unit[1]}`;
  return seconds >= 0 ? `in ${label}` : `${label} ago`;
}

function marketSentimentSummary(news: NewsEvent[]): { label: string; tone: string } {
  const scored = news.filter((n) => n.sentiment !== "unknown");
  if (scored.length === 0) return { label: "No data", tone: "text-ink-500" };
  const bullish = scored.filter((n) => n.sentiment === "bullish" || n.sentiment === "very_bullish").length;
  const bearish = scored.filter((n) => n.sentiment === "bearish" || n.sentiment === "very_bearish").length;
  if (bullish === bearish) return { label: "Mixed", tone: "text-ink-500" };
  const bullishShare = bullish / scored.length;
  if (bullish > bearish) return { label: `Bullish ${Math.round(bullishShare * 100)}%`, tone: "text-signal-green" };
  return { label: `Bearish ${Math.round((1 - bullishShare) * 100)}%`, tone: "text-signal-red" };
}

function newsMomentumSummary(news: NewsEvent[]): { label: string; tone: string } {
  const highImportance = news.filter((n) => n.importance === "high" || n.importance === "critical").length;
  if (news.length >= 6 || highImportance >= 2) return { label: "High", tone: "text-signal-red" };
  if (news.length >= 2 || highImportance >= 1) return { label: "Medium", tone: "text-signal-yellow" };
  return { label: "Low", tone: "text-ink-500" };
}

export function NewsIntelligenceCenter({
  news,
  macroEvents,
  newsRisk,
  aiServicesConfigured,
}: {
  news: NewsEvent[];
  macroEvents: MacroEvent[];
  newsRisk: NewsRisk | null;
  aiServicesConfigured: boolean;
}) {
  const sentiment = marketSentimentSummary(news);
  const momentum = newsMomentumSummary(news);
  const avgSourceQuality = news.length > 0 ? Math.round(news.reduce((s, n) => s + n.source_quality_score, 0) / news.length) : null;
  const upcomingMacro = macroEvents
    .filter((m) => m.status === "scheduled")
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .slice(0, 6);

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">
          News Intelligence Center {news.length > 0 ? `(${news.length})` : ""}
        </p>
        {newsRisk && (
          <span
            className={`inline-block rounded border px-2 py-1 text-xs font-medium uppercase tracking-wide ${RISK_LEVEL_COLOR[newsRisk.level] ?? RISK_LEVEL_COLOR.normal}`}
            title={newsRisk.reasons.join("; ") || "No elevated news/macro risk"}
          >
            Event Risk: {newsRisk.level}
          </span>
        )}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-base-700 bg-base-900 p-3">
          <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Market Sentiment</p>
          <p className={`text-sm font-semibold ${sentiment.tone}`}>{sentiment.label}</p>
        </div>
        <div className="rounded-lg border border-base-700 bg-base-900 p-3">
          <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">News Momentum</p>
          <p className={`text-sm font-semibold ${momentum.tone}`}>{momentum.label}</p>
        </div>
        <div className="rounded-lg border border-base-700 bg-base-900 p-3">
          <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Source Quality</p>
          <p className="text-sm font-semibold text-ink-100">{avgSourceQuality !== null ? `${avgSourceQuality}/100` : "—"}</p>
        </div>
        <div className="rounded-lg border border-base-700 bg-base-900 p-3">
          <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Upcoming Macro</p>
          <p className="text-sm font-semibold text-ink-100">{upcomingMacro.length}</p>
        </div>
      </div>

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Upcoming Macro Events</p>
      {upcomingMacro.length > 0 ? (
        <div className="mb-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-ink-500">
                <th className="pb-2 pr-3 font-normal">Event</th>
                <th className="pb-2 pr-3 font-normal">Country</th>
                <th className="pb-2 pr-3 font-normal">When</th>
                <th className="pb-2 pr-3 font-normal">Importance</th>
                <th className="pb-2 pr-3 font-normal">Forecast</th>
                <th className="pb-2 font-normal">Previous</th>
              </tr>
            </thead>
            <tbody>
              {upcomingMacro.map((m) => (
                <tr key={m.id} className="border-t border-base-700/60 hover:bg-base-800">
                  <td className="py-1.5 pr-3 text-ink-100">{m.event}</td>
                  <td className="py-1.5 pr-3 text-ink-300">
                    {m.country}
                    {m.currency ? ` (${m.currency})` : ""}
                  </td>
                  <td className="py-1.5 pr-3 text-ink-300">{timeRelative(m.scheduled_at)}</td>
                  <td className={`py-1.5 pr-3 uppercase ${IMPORTANCE_COLOR[m.importance] ?? "text-ink-500"}`}>{m.importance}</td>
                  <td className="py-1.5 pr-3 text-ink-300">{m.forecast ?? "—"}</td>
                  <td className="py-1.5 text-ink-300">{m.previous ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mb-4 text-xs text-ink-500">No upcoming macro events in the calendar window.</p>
      )}

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Latest Events</p>
      {news.length > 0 ? (
        <div className="space-y-2">
          {news.map((n) => (
            <div key={n.id} className="rounded border border-base-700 px-2 py-1.5 text-xs">
              <div className="flex items-center justify-between text-ink-100">
                <span>{n.headline}</span>
                <span className="shrink-0 pl-2 text-ink-500">{n.source}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wide">
                <span className={SENTIMENT_COLOR[n.sentiment] ?? "text-ink-500"}>{n.sentiment.replace("_", " ")}</span>
                <span className={IMPORTANCE_COLOR[n.importance] ?? "text-ink-500"}>{n.importance}</span>
                <span className="text-ink-500">quality {Math.round(n.source_quality_score)}</span>
                {n.has_conflicting_sources && <span className="text-signal-yellow">conflicting sources</span>}
              </div>
              {n.impacts.length > 0 ? (
                <div className="mt-1 flex flex-wrap gap-2">
                  {n.impacts.map((impact, i) => (
                    <span
                      key={i}
                      className={`text-[10px] uppercase tracking-wide ${
                        impact.direction === "bullish"
                          ? "text-signal-green"
                          : impact.direction === "bearish"
                            ? "text-signal-red"
                            : "text-ink-500"
                      }`}
                    >
                      {impact.asset_symbol} {impact.direction} ({impact.impact}, {Math.round(impact.confidence * 100)}%
                      {impact.is_direct ? "" : ", indirect"})
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-1 text-[10px] text-ink-500">
                  No asset impact interpreted{aiServicesConfigured ? " yet" : " — AI services not configured"}.
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-ink-500">No recent news.</p>
      )}
    </section>
  );
}
