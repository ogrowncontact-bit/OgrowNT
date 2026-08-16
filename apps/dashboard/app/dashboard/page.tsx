import { cookies } from "next/headers";
import {
  getAlerts,
  getAnalyticsOverview,
  getAssets,
  getBacktests,
  getHealth,
  getLearnedRules,
  getNews,
  getOpportunities,
  getPortfolio,
  getPositions,
  getPromotionCheck,
  getRegimes,
  getStrategyLearning,
  getSystemStatus,
  getTradeJournal,
  getTrades,
} from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { RiskBadge } from "@/components/RiskBadge";
import { RegimeBadge } from "@/components/RegimeBadge";
import { TierBadge } from "@/components/TierBadge";
import { LifecycleBadge } from "@/components/LifecycleBadge";
import { LogoutButton } from "@/components/LogoutButton";
import { EquitySparkline } from "@/components/EquitySparkline";

export const dynamic = "force-dynamic";

const eur = (n: number) =>
  new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(n);

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [health, status, portfolio, assets, positions, opportunities, regimes, trades, news, strategyLearning, tradeJournal, learnedRules, alerts] =
    await Promise.all([
      getHealth(),
      getSystemStatus(token),
      getPortfolio(token),
      getAssets(token),
      getPositions(token, "open"),
      getOpportunities(token, 10),
      getRegimes(token),
      getTrades(token, 8),
      getNews(token, 6),
      getStrategyLearning(token),
      getTradeJournal(token, 6),
      getLearnedRules(token, 6),
      getAlerts(token, 8),
    ]);

  const [backtests, promotionChecks, analytics] = await Promise.all([
    getBacktests(token, 8),
    Promise.all((strategyLearning ?? []).map((s) => getPromotionCheck(token, s.strategy_id))),
    getAnalyticsOverview(token),
  ]);
  const promotionByStrategyId = new Map(
    (strategyLearning ?? []).map((s, i) => [s.strategy_id, promotionChecks[i]])
  );

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
          News {news ? `(${news.length})` : ""}
        </p>
        {news && news.length > 0 ? (
          <div className="space-y-2">
            {news.map((n) => (
              <div key={n.id} className="rounded border border-base-700 px-2 py-1.5 text-xs">
                <div className="flex items-center justify-between text-ink-100">
                  <span>{n.headline}</span>
                  <span className="shrink-0 pl-2 text-ink-500">{n.source}</span>
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
                        {impact.asset_symbol} {impact.direction} ({impact.impact}, {Math.round(impact.confidence * 100)}%)
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1 text-[10px] text-ink-500">
                    No asset impact interpreted{" "}
                    {health?.components.find((c) => c.name === "ai_services")?.status === "yellow"
                      ? "— AI services not configured"
                      : "yet"}
                    .
                  </p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No recent news.</p>
        )}
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

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-base-700 bg-base-900 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
            Strategy Health {strategyLearning ? `(${strategyLearning.length})` : ""}
          </p>
          {strategyLearning && strategyLearning.length > 0 ? (
            <div className="space-y-2">
              {strategyLearning.map((s) => {
                const promotion = promotionByStrategyId.get(s.strategy_id);
                return (
                  <div key={s.strategy_id} className="rounded border border-base-700 px-2 py-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-ink-100">{s.strategy_code}</span>
                      <div className="flex items-center gap-2">
                        <LifecycleBadge stage={s.lifecycle_stage} />
                        <span
                          className={
                            s.health_score === null
                              ? "text-ink-500"
                              : s.health_score >= 60
                                ? "text-signal-green"
                                : s.health_score >= 35
                                  ? "text-signal-yellow"
                                  : "text-signal-red"
                          }
                        >
                          {s.health_score !== null ? s.health_score.toFixed(1) : "—"}
                        </span>
                      </div>
                    </div>
                    <div className="mt-1 flex justify-between text-ink-500">
                      <span>{s.total_trades} trades closed</span>
                      <span>
                        win rate {s.win_rate !== null ? `${Math.round(s.win_rate * 100)}%` : "—"} · expectancy{" "}
                        {s.expectancy !== null ? s.expectancy.toFixed(2) + "R" : "—"}
                      </span>
                    </div>
                    {promotion && promotion.next_stage && (
                      <div
                        className={`mt-1 text-[10px] ${promotion.eligible ? "text-signal-green" : "text-ink-500"}`}
                        title={promotion.eligible ? undefined : promotion.reasons.join("; ")}
                      >
                        {promotion.eligible
                          ? `Ready for promotion -> ${promotion.next_stage}`
                          : `Not yet ready for ${promotion.next_stage} (${promotion.reasons.length} unmet criteria)`}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-ink-500">No strategies registered.</p>
          )}
        </div>

        <div className="rounded-lg border border-base-700 bg-base-900 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
            Learned Rules {learnedRules ? `(${learnedRules.length})` : ""}
          </p>
          {learnedRules && learnedRules.length > 0 ? (
            <div className="space-y-2">
              {learnedRules.map((r) => (
                <div key={r.id} className="rounded border border-base-700 px-2 py-1.5 text-xs">
                  <div className="flex items-center justify-between text-ink-100">
                    <span>{r.scope}</span>
                    <span
                      className={`text-[10px] uppercase tracking-wide ${
                        r.status === "validated"
                          ? "text-signal-green"
                          : r.status === "rejected"
                            ? "text-signal-red"
                            : "text-signal-yellow"
                      }`}
                    >
                      {r.status}
                    </span>
                  </div>
                  <p className="mt-1 text-ink-500">{r.conclusion}</p>
                  <p className="mt-1 text-[10px] text-ink-500">
                    confidence {Math.round(r.confidence * 100)}% · sample {r.sample_size}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-ink-500">
              No candidate rules yet — the Research Agent proposes these once a pattern or
              strategy has enough closed trades to look underperforming (docs/blueprint/
              04-agents-architecture.md#agent-14).
            </p>
          )}
        </div>
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
          Trade Journal {tradeJournal ? `(${tradeJournal.length})` : ""}
        </p>
        {tradeJournal && tradeJournal.length > 0 ? (
          <div className="space-y-2">
            {tradeJournal.map((j) => (
              <div key={j.trade_id} className="rounded border border-base-700 px-2 py-1.5 text-xs">
                <div className="flex items-center justify-between text-ink-100">
                  <span>
                    {j.asset_symbol} · {j.strategy_code}
                  </span>
                  <span className={j.actual_outcome === "win" ? "text-signal-green" : "text-signal-red"}>
                    expected {j.expected_outcome} → actual {j.actual_outcome}
                  </span>
                </div>
                {j.hypothesis ? (
                  <p className="mt-1 text-ink-500">
                    {j.hypothesis} <span className="text-[10px]">({j.root_cause})</span>
                  </p>
                ) : (
                  <p className="mt-1 text-[10px] text-ink-500">
                    {j.actual_outcome === "win" ? "Matched expectation — no hypothesis needed." : "No hypothesis — AI services not configured."}
                  </p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No journal entries yet — none closed.</p>
        )}
      </section>

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-base-700 bg-base-900 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
            Equity Curve {analytics ? `(${analytics.equity_curve.length} snapshots)` : ""}
          </p>
          {analytics ? (
            <>
              <EquitySparkline points={analytics.equity_curve} />
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink-500">
                <span>Peak equity: {analytics.drawdown.peak_equity !== null ? eur(analytics.drawdown.peak_equity) : "—"}</span>
                <span>Max drawdown: {analytics.drawdown.max_drawdown_pct !== null ? `${analytics.drawdown.max_drawdown_pct.toFixed(2)}%` : "—"}</span>
                <span>Trades: {analytics.trade_stats.total_trades}</span>
                <span>
                  Win rate: {analytics.trade_stats.win_rate !== null ? `${Math.round(analytics.trade_stats.win_rate * 100)}%` : "—"} ·
                  Expectancy: {analytics.trade_stats.expectancy !== null ? `${analytics.trade_stats.expectancy.toFixed(2)}R` : "—"}
                </span>
              </div>
            </>
          ) : (
            <p className="text-xs text-ink-500">DATA_UNAVAILABLE</p>
          )}
        </div>

        <div className="rounded-lg border border-base-700 bg-base-900 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
            Opportunity Tiers (30d) &amp; Regime Mix (7d)
          </p>
          {analytics && Object.keys(analytics.tier_distribution).length > 0 ? (
            <div className="mb-3 space-y-1">
              {Object.entries(analytics.tier_distribution).map(([tier, count]) => (
                <div key={tier} className="flex items-center gap-2 text-xs">
                  <span className="w-24 shrink-0">
                    <TierBadge tier={tier} />
                  </span>
                  <span className="text-ink-500">{count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="mb-3 text-xs text-ink-500">No scored opportunities in the last 30 days.</p>
          )}
          {analytics && Object.keys(analytics.regime_distribution).length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {Object.entries(analytics.regime_distribution).map(([regime, count]) => (
                <span key={regime} className="flex items-center gap-1">
                  <RegimeBadge regime={regime} />
                  <span className="text-[10px] text-ink-500">{count}</span>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-ink-500">No regime reads in the last 7 days.</p>
          )}
        </div>
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
          Pattern Leaderboard {analytics ? `(${analytics.pattern_leaderboard.length})` : ""}
        </p>
        {analytics && analytics.pattern_leaderboard.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-ink-500">
                  <th className="pb-2 pr-3 font-normal">Pattern</th>
                  <th className="pb-2 pr-3 font-normal">Regime</th>
                  <th className="pb-2 pr-3 font-normal">Sample</th>
                  <th className="pb-2 pr-3 font-normal">Win Rate</th>
                  <th className="pb-2 font-normal">Expectancy</th>
                </tr>
              </thead>
              <tbody>
                {analytics.pattern_leaderboard.map((p, i) => (
                  <tr key={`${p.pattern_type}-${p.regime}-${i}`} className="border-t border-base-700/60 hover:bg-base-800">
                    <td className="py-1.5 pr-3 text-ink-100">{p.pattern_type.replace(/_/g, " ")}</td>
                    <td className="py-1.5 pr-3">
                      <RegimeBadge regime={p.regime} />
                    </td>
                    <td className="py-1.5 pr-3 text-ink-300">{p.sample_size}</td>
                    <td className="py-1.5 pr-3 text-ink-300">{p.win_rate !== null ? `${Math.round(p.win_rate * 100)}%` : "—"}</td>
                    <td className={`py-1.5 ${(p.expectancy ?? 0) > 0 ? "text-signal-green" : (p.expectancy ?? 0) < 0 ? "text-signal-red" : "text-ink-300"}`}>
                      {p.expectancy !== null ? `${p.expectancy.toFixed(2)}R` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-ink-500">No pattern performance recorded yet.</p>
        )}
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
          Backtests {backtests ? `(${backtests.length})` : ""}
        </p>
        {backtests && backtests.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-ink-500">
                  <th className="pb-2 pr-3 font-normal">Strategy</th>
                  <th className="pb-2 pr-3 font-normal">Asset</th>
                  <th className="pb-2 pr-3 font-normal">Kind</th>
                  <th className="pb-2 pr-3 font-normal">Trades</th>
                  <th className="pb-2 pr-3 font-normal">Net Return</th>
                  <th className="pb-2 pr-3 font-normal">Win Rate</th>
                  <th className="pb-2 font-normal">Max DD</th>
                </tr>
              </thead>
              <tbody>
                {backtests.map((b) => (
                  <tr key={b.id} className="border-t border-base-700/60 hover:bg-base-800">
                    <td className="py-1.5 pr-3 text-ink-100">{b.strategy_code}</td>
                    <td className="py-1.5 pr-3 text-ink-300">{b.asset_symbol}</td>
                    <td className="py-1.5 pr-3 text-ink-500">
                      {b.kind === "walk_forward_window" ? `wf ${(b.window_index ?? 0) + 1}/${b.total_windows}` : b.kind}
                    </td>
                    <td className="py-1.5 pr-3 text-ink-300">{b.num_trades}</td>
                    <td className={`py-1.5 pr-3 ${(b.net_return ?? 0) > 0 ? "text-signal-green" : (b.net_return ?? 0) < 0 ? "text-signal-red" : "text-ink-300"}`}>
                      {b.net_return !== null ? `${(b.net_return * 100).toFixed(2)}%` : "—"}
                    </td>
                    <td className="py-1.5 pr-3 text-ink-300">{b.win_rate !== null ? `${Math.round(b.win_rate * 100)}%` : "—"}</td>
                    <td className="py-1.5 text-ink-300">{b.max_drawdown !== null ? `${b.max_drawdown.toFixed(2)}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-ink-500">
            No backtests run yet — launch one via <code>POST /api/backtests</code> (see <code>/docs</code>).
          </p>
        )}
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
          Alerts {alerts ? `(${alerts.length})` : ""}
        </p>
        {alerts && alerts.length > 0 ? (
          <div className="space-y-2">
            {alerts.map((a) => (
              <div key={a.id} className="rounded border border-base-700 px-2 py-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span
                    className={`text-[10px] uppercase tracking-wide ${
                      a.severity === "critical"
                        ? "text-signal-red"
                        : a.severity === "warning"
                          ? "text-signal-yellow"
                          : "text-ink-500"
                    }`}
                  >
                    {a.severity} · {a.category}
                  </span>
                  <span className="text-ink-500">
                    {a.acknowledged ? "acknowledged" : a.delivered_at ? "delivered" : "pending delivery"}
                  </span>
                </div>
                <p className="mt-1 text-ink-100">{a.message}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No alerts — nothing has needed the admin&apos;s attention yet.</p>
        )}
      </section>

      <section className="rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">System Health</p>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {health?.components.map((c) => (
            <div key={c.name} className="flex items-center gap-2 text-xs" title={c.detail ?? undefined}>
              <span
                className={`h-2 w-2 rounded-full ${
                  c.status === "green"
                    ? "bg-signal-green"
                    : c.status === "yellow"
                      ? "bg-signal-yellow"
                      : "bg-signal-red"
                }`}
              />
              <span className="text-ink-300">{c.name.replace(/_/g, " ")}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
