import { cookies } from "next/headers";
import { getDashboardLearning } from "@/lib/api";
import { LifecycleBadge } from "@/components/LifecycleBadge";

export const dynamic = "force-dynamic";

// Learning Center — "PROMPT 14" §43-45. §45's Learning Safety boundary
// holds structurally, not just by convention: this page only ever reads
// StrategyPerformance/TradeJournal rows (packages/quant/learning/), and
// nothing the Learning Agent writes touches SystemState.trading_enabled,
// kill_switch_state, live-trading permissions, or risk_limits.yaml — those
// remain exclusively packages/risk's and an admin's to change (see
// tests/test_command_center_red_team.py for the structural proof).
export default async function LearningPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const data = await getDashboardLearning(token);

  return (
    <div>
      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Learning Safety</p>
        <p className="text-[10px] text-ink-500">
          The Learning Engine cannot alter risk limits, the kill switch, live-trading permissions, or capital safety
          floors — it only ever reads/writes strategy performance and trade-journal rows.
        </p>
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">What the system learned</p>
        {data && data.strategy_performance.length > 0 ? (
          <div className="space-y-1">
            {data.strategy_performance.map((s) => (
              <div key={s.strategy_id} className="flex items-center justify-between rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
                <span className="text-ink-100">{s.strategy_code}</span>
                <LifecycleBadge stage={s.lifecycle_stage} />
                <span className="text-ink-500">{s.total_trades} trades</span>
                <span className="text-ink-300">health {s.health_score?.toFixed(0) ?? "—"}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No strategy performance recorded yet.</p>
        )}
      </section>

      <section className="rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Trade Journal</p>
        {data && data.trade_journal.length > 0 ? (
          <div className="space-y-2">
            {data.trade_journal.map((j) => (
              <div key={j.trade_id} className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
                <p className="text-ink-100">
                  {j.asset_symbol} <span className="text-ink-500">({j.strategy_code})</span>
                </p>
                <p className="text-ink-300">
                  expected: {j.expected_outcome} · actual: {j.actual_outcome}
                </p>
                {j.hypothesis && <p className="text-ink-500">hypothesis: {j.hypothesis}</p>}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No journal entries yet.</p>
        )}
      </section>
    </div>
  );
}
