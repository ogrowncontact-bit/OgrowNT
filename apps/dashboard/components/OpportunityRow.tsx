"use client";

import { useState } from "react";
import { RegimeBadge } from "@/components/RegimeBadge";
import { TierBadge } from "@/components/TierBadge";
import type { Opportunity, OpportunityDetail } from "@/lib/api";

export function OpportunityRow({ opportunity: o }: { opportunity: Opportunity }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<OpportunityDetail | null>(null);
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
      const res = await fetch(`/api/opportunity-detail?signal_id=${o.signal_id}`);
      if (res.ok) setDetail(await res.json());
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <tr
        className="cursor-pointer border-t border-base-700/60 hover:bg-base-800"
        onClick={toggle}
        title="Click for why this opportunity exists"
      >
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
        <td className="py-1.5 pr-3 text-ink-300">{Math.round(o.confidence)}%</td>
        <td className="py-1.5">
          <TierBadge tier={o.tier} />
        </td>
      </tr>
      {expanded && (
        <tr className="border-t border-base-700/60 bg-base-950/60">
          <td colSpan={8} className="px-3 py-3">
            <p className="mb-2 text-[10px] uppercase tracking-wider text-ink-500">
              Why this opportunity exists
            </p>
            {loading && <p className="text-xs text-ink-500">Loading…</p>}
            {!loading && detail && detail.evidence.length > 0 && (
              <ul className="space-y-1">
                {detail.evidence.map((item, i) => (
                  <li
                    key={i}
                    className={`text-xs ${item.kind === "confirm" ? "text-signal-green" : "text-signal-yellow"}`}
                  >
                    {item.kind === "confirm" ? "✓" : "⚠"} {item.text}
                  </li>
                ))}
              </ul>
            )}
            {!loading && detail && detail.evidence.length === 0 && (
              <p className="text-xs text-ink-500">No structured evidence recorded for this opportunity.</p>
            )}
            {!loading && !detail && <p className="text-xs text-signal-red">Could not load evidence.</p>}
          </td>
        </tr>
      )}
    </>
  );
}
