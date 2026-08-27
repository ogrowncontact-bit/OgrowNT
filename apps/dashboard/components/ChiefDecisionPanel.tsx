"use client";

import { useState } from "react";
import { DecisionStateBadge } from "@/components/DecisionStateBadge";
import type { Decision, DecisionDetail } from "@/lib/api";

// Chief Decision Engine + Agent Consensus + Decision Trace/Explainability —
// "PROMPT 14" §17-21, §74-77. A compact tally (BULLISH/NEUTRAL/BEARISH,
// derived from decision_state — the same closed vocabulary
// packages/agents/chief.py already produces, never re-classified here)
// plus the most recent decisions, each expandable into its real
// explainability trace: Decision.agent_inputs IS the full per-agent record
// Prompt 9's Chief Decision Engine already computed (see that model's own
// docstring, packages/shared/models.py) — reused via the existing
// /api/decision-detail Route Handler (apps/dashboard/app/api/
// decision-detail/route.ts, built for AICommandCenter), not a second
// explainability implementation. The full per-agent roster/reliability
// view lives on /command-center/agents (AICommandCenter) — this panel is
// deliberately the compact, "what changed most recently" surface.
const BULLISH = new Set(["strong_long_bias", "long_bias"]);
const BEARISH = new Set(["strong_short_bias", "short_bias"]);

export function ChiefDecisionPanel({ decisions }: { decisions: Decision[] }) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DecisionDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const bullish = decisions.filter((d) => BULLISH.has(d.decision_state)).length;
  const bearish = decisions.filter((d) => BEARISH.has(d.decision_state)).length;
  const neutral = decisions.length - bullish - bearish;

  async function toggle(decision: Decision) {
    if (expandedId === decision.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(decision.id);
    setDetail(null);
    setLoading(true);
    try {
      const res = await fetch(`/api/decision-detail?decision_id=${decision.id}`);
      if (res.ok) setDetail(await res.json());
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">Chief Decision Engine</p>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="text-signal-green">BULLISH {bullish}</span>
          <span className="text-ink-500">NEUTRAL {neutral}</span>
          <span className="text-signal-red">BEARISH {bearish}</span>
        </div>
      </div>
      {decisions.length === 0 && <p className="text-xs text-ink-500">No decisions recorded yet this cycle.</p>}
      <div className="space-y-1.5">
        {decisions.slice(0, 10).map((d) => (
          <div key={d.id} className="rounded border border-base-700/60">
            <button
              onClick={() => toggle(d)}
              className="flex w-full items-center justify-between px-2.5 py-1.5 text-left text-xs hover:bg-base-800"
            >
              <span className="flex items-center gap-2">
                <span className="text-ink-100">{d.asset_symbol}</span>
                <DecisionStateBadge state={d.decision_state} />
                {d.critical_agent_failure && <span className="text-signal-red">⚠ agent failure</span>}
              </span>
              {/* consensus_score is already -100..100 (packages/agents/consensus.py's own
                  docstring) -- -100 max-conviction short, +100 max-conviction long -- never
                  multiply by 100 again. */}
              <span className="text-ink-500">consensus {d.consensus_score.toFixed(0)}</span>
            </button>
            {expandedId === d.id && (
              <div className="border-t border-base-700/60 px-2.5 py-2 text-[11px]">
                <p className="mb-1 text-ink-300">{d.reasoning_summary}</p>
                {d.blocked_reason && <p className="mb-1 text-signal-red">Blocked: {d.blocked_reason}</p>}
                {loading && <p className="text-ink-500">Loading agent trace…</p>}
                {!loading && detail && detail.id === d.id && (
                  <div className="mt-1 space-y-1">
                    <p className="text-[10px] uppercase tracking-wider text-ink-500">
                      Agent inputs ({Object.keys(detail.agent_inputs).length})
                    </p>
                    <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 md:grid-cols-3">
                      {Object.entries(detail.agent_inputs).map(([code, msg]) => (
                        <p key={code} className="truncate text-ink-300">
                          <span className="text-ink-500">{code}:</span> {msg.signal} ({Math.round(msg.confidence)}%)
                        </p>
                      ))}
                    </div>
                    {detail.contradictions.length > 0 && (
                      <p className="mt-1 text-signal-yellow">
                        {detail.contradictions.length} agent disagreement(s) detected
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
