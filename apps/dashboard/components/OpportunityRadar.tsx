import { OpportunityRow } from "@/components/OpportunityRow";
import type { Opportunity } from "@/lib/api";

// Opportunity Radar — "PROMPT 14" §11-16: real-time top opportunities,
// ranked by risk-adjusted score (final_score already IS that composite —
// packages/quant/scoring/engine.py, unchanged since Phase 2/Prompt 11 —
// never raw expected return alone). Reuses OpportunityRow's own
// click-to-expand "why this opportunity exists" trace (§16) rather than a
// second explainability implementation.
export function OpportunityRadar({ opportunities }: { opportunities: Opportunity[] }) {
  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
        Opportunity Radar {opportunities.length ? `(top ${opportunities.length})` : ""}
      </p>
      {opportunities.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wide text-ink-500">
                <th className="pb-2 pr-3 font-normal">Asset</th>
                <th className="pb-2 pr-3 font-normal">Strategy</th>
                <th className="pb-2 pr-3 font-normal">Dir</th>
                <th className="pb-2 pr-3 font-normal">Regime</th>
                <th className="pb-2 pr-3 font-normal">R:R</th>
                <th className="pb-2 pr-3 font-normal">Score</th>
                <th className="pb-2 pr-3 font-normal">Conf</th>
                <th className="pb-2 font-normal">Tier</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.map((o) => (
                <OpportunityRow key={o.signal_id} opportunity={o} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-xs text-ink-500">No opportunities above the ignore tier right now.</p>
      )}
    </section>
  );
}
