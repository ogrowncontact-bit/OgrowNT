"use client";

import { useState } from "react";
import { DecisionStateBadge } from "@/components/DecisionStateBadge";
import type { Decision, DecisionDetail } from "@/lib/api";

const SIGNAL_COLOR: Record<string, string> = {
  strong_long: "text-signal-green",
  long: "text-signal-green",
  neutral: "text-ink-500",
  short: "text-signal-red",
  strong_short: "text-signal-red",
  no_read: "text-ink-500",
};

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

export function DecisionRow({ decision: d }: { decision: Decision }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<DecisionDetail | null>(null);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setExpanded(true);
    if (detail) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/decision-detail?decision_id=${d.id}`);
      if (res.ok) setDetail(await res.json());
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <tr className="cursor-pointer border-t border-base-700/60 hover:bg-base-800" onClick={toggle} title="Click for the full agent decision trace">
        <td className="py-1.5 pr-3 text-ink-100">{d.asset_symbol}</td>
        <td className="py-1.5 pr-3">
          <DecisionStateBadge state={d.decision_state} />
        </td>
        <td className="py-1.5 pr-3 text-ink-300">{d.consensus_score.toFixed(1)}</td>
        <td className="py-1.5 pr-3 text-ink-300">{d.contradiction_score.toFixed(1)}</td>
        <td className="py-1.5 pr-3 text-ink-500">{timeAgo(d.ts)}</td>
        <td className="py-1.5 text-ink-300">{d.reasoning_summary}</td>
      </tr>
      {expanded && (
        <tr className="border-t border-base-700/60 bg-base-950/60">
          <td colSpan={6} className="px-3 py-3">
            <p className="mb-2 text-[10px] uppercase tracking-wider text-ink-500">Decision trace — all 18 agent inputs</p>
            {loading && <p className="text-xs text-ink-500">Loading…</p>}
            {!loading && detail && (
              <>
                <div className="mb-3 overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="text-ink-500">
                        <th className="pb-1 pr-3 font-normal">Agent</th>
                        <th className="pb-1 pr-3 font-normal">Status</th>
                        <th className="pb-1 pr-3 font-normal">Signal</th>
                        <th className="pb-1 pr-3 font-normal">Confidence</th>
                        <th className="pb-1 font-normal">Rationale</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(detail.agent_inputs).map(([code, m]) => (
                        <tr key={code} className="border-t border-base-800">
                          <td className="py-1 pr-3 text-ink-100">{code}</td>
                          <td className="py-1 pr-3 text-ink-500">{m.status}</td>
                          <td className={`py-1 pr-3 uppercase ${SIGNAL_COLOR[m.signal] ?? "text-ink-500"}`}>{m.signal.replace("_", " ")}</td>
                          <td className="py-1 pr-3 text-ink-300">{Math.round(m.confidence * 100)}%</td>
                          <td className="py-1 text-ink-500">{m.rationale ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {detail.contradictions.length > 0 && (
                  <div>
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Contradictions in this decision</p>
                    <ul className="space-y-1">
                      {detail.contradictions.map((c) => (
                        <li key={c.id} className="text-xs text-signal-yellow">
                          ⚠ {c.description} (severity {c.severity.toFixed(0)})
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {d.blocked_reason && <p className="mt-2 text-xs text-signal-red">Blocked reason: {d.blocked_reason}</p>}
              </>
            )}
            {!loading && !detail && <p className="text-xs text-signal-red">Could not load decision trace.</p>}
          </td>
        </tr>
      )}
    </>
  );
}
