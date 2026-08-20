import { DecisionRow } from "@/components/DecisionRow";
import { DecisionStateBadge } from "@/components/DecisionStateBadge";
import { RestoreAgentButton } from "@/components/RestoreAgentButton";
import type { Agent, Contradiction, Decision } from "@/lib/api";

// AI Command Center — "PROMPT 9" §47-50: agent roster (status/confidence/
// reliability/last-analysis), market consensus per asset, contradictions,
// and current decisions with a full explainability trace on click.

const STATUS_COLOR: Record<string, string> = {
  active: "text-signal-green",
  quarantined: "text-signal-red",
  disabled: "text-ink-500",
};

function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

function latestDecisionPerAsset(decisions: Decision[]): Decision[] {
  const seen = new Map<string, Decision>();
  for (const d of decisions) {
    if (!seen.has(d.asset_symbol)) seen.set(d.asset_symbol, d); // decisions arrive newest-first
  }
  return Array.from(seen.values());
}

export function AICommandCenter({
  agents,
  decisions,
  contradictions,
}: {
  agents: Agent[];
  decisions: Decision[];
  contradictions: Contradiction[];
}) {
  const consensus = latestDecisionPerAsset(decisions);
  const activeCount = agents.filter((a) => a.status === "active").length;
  const quarantinedCount = agents.filter((a) => a.status === "quarantined").length;
  const criticalFailures = decisions.slice(0, 20).filter((d) => d.critical_agent_failure).length;

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">AI Command Center ({agents.length} agents)</p>
        <span className="text-xs text-ink-500">
          {activeCount} active · {quarantinedCount} quarantined{criticalFailures > 0 ? ` · ${criticalFailures} critical failures (last 20)` : ""}
        </span>
      </div>

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Market Consensus</p>
      {consensus.length > 0 ? (
        <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          {consensus.map((d) => (
            <div key={d.asset_symbol} className="rounded-lg border border-base-700 bg-base-900 p-2">
              <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">{d.asset_symbol}</p>
              <DecisionStateBadge state={d.decision_state} />
              <p className="mt-1 text-[10px] text-ink-500">consensus {d.consensus_score.toFixed(0)}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mb-4 text-xs text-ink-500">No decisions yet — the worker&apos;s next cycle will populate this.</p>
      )}

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Agent Roster</p>
      <div className="mb-4 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="text-ink-500">
              <th className="pb-2 pr-3 font-normal">Agent</th>
              <th className="pb-2 pr-3 font-normal">Type</th>
              <th className="pb-2 pr-3 font-normal">Status</th>
              <th className="pb-2 pr-3 font-normal">Reliability</th>
              <th className="pb-2 pr-3 font-normal">Last Analysis</th>
              <th className="pb-2 font-normal"></th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => (
              <tr key={a.code} className="border-t border-base-700/60">
                <td className="py-1.5 pr-3 text-ink-100">{a.name}</td>
                <td className="py-1.5 pr-3 text-ink-500">{a.directional ? "directional" : "advisory"}</td>
                <td className={`py-1.5 pr-3 uppercase ${STATUS_COLOR[a.status] ?? "text-ink-500"}`} title={a.quarantine_reason ?? undefined}>
                  {a.status}
                </td>
                <td className="py-1.5 pr-3 text-ink-300">
                  {a.reliability?.reliability_score != null
                    ? `${a.reliability.reliability_score.toFixed(0)}/100 (n=${a.reliability.sample_size})`
                    : "insufficient data"}
                </td>
                <td className="py-1.5 pr-3 text-ink-500">{timeAgo(a.last_seen_at)}</td>
                <td className="py-1.5">{a.status === "quarantined" && <RestoreAgentButton code={a.code} name={a.name} />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Recent Decisions</p>
      {decisions.length > 0 ? (
        <div className="mb-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-ink-500">
                <th className="pb-2 pr-3 font-normal">Asset</th>
                <th className="pb-2 pr-3 font-normal">Decision</th>
                <th className="pb-2 pr-3 font-normal">Consensus</th>
                <th className="pb-2 pr-3 font-normal">Contradiction</th>
                <th className="pb-2 pr-3 font-normal">When</th>
                <th className="pb-2 font-normal">Reasoning</th>
              </tr>
            </thead>
            <tbody>
              {decisions.map((d) => (
                <DecisionRow key={d.id} decision={d} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mb-4 text-xs text-ink-500">No decisions recorded yet.</p>
      )}

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Detected Conflicts</p>
      {contradictions.length > 0 ? (
        <ul className="space-y-1">
          {contradictions.map((c) => (
            <li key={c.id} className="text-xs text-signal-yellow">
              ⚠ {c.description} (severity {c.severity.toFixed(0)})
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-ink-500">No agent contradictions detected in recent cycles.</p>
      )}
    </section>
  );
}
