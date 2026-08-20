import { ApprovalDecisionButtons } from "@/components/ApprovalDecisionButtons";
import type { ResearchReport } from "@/lib/api";

// Autonomous Research Lab — "PROMPT 10" §90-91: the research pipeline's own
// dashboard surface, built entirely from GET /api/research-lab/report (the
// same 11-section report packages.research.report.generate_research_report
// produces). Nothing on this panel can change production state by itself —
// the ONLY interactive elements are the pending-approval decision buttons,
// which go through the same human-reviewer-required
// packages.research.approval workflow the API enforces server-side.

const LIFECYCLE_COLOR: Record<string, string> = {
  champion: "text-signal-green",
  challenger: "text-signal-yellow",
  production_candidate: "text-signal-yellow",
  experimental: "text-ink-500",
  rolled_back: "text-signal-red",
  retired: "text-ink-500",
};

const SEVERITY_COLOR: Record<string, string> = {
  high: "text-signal-red",
  medium: "text-signal-yellow",
  low: "text-ink-500",
  none: "text-ink-500",
};

const EXPERIMENT_STATUS_COLOR: Record<string, string> = {
  promising: "text-signal-green",
  validating: "text-signal-green",
  approved: "text-signal-green",
  rejected: "text-signal-red",
  quarantined: "text-signal-red",
  failed: "text-signal-red",
  running: "text-signal-yellow",
  queued: "text-ink-500",
};

function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function AutonomousResearchLab({ report }: { report: ResearchReport | null }) {
  if (!report) {
    return (
      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">Autonomous Research Lab</p>
        <p className="mt-2 text-xs text-ink-500">Research report unavailable — the API may be unreachable.</p>
      </section>
    );
  }

  const s = report.executive_summary;
  const budgetEntries = Object.entries(report.research_budget_usage);

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">Autonomous Research Lab</p>
        <span className="text-xs text-ink-500">
          {s.total_hypotheses} hypotheses · {s.total_experiments_recent_window} experiments ·{" "}
          {s.promising_or_better_recent_window} promising+
        </span>
      </div>

      <p className="mb-1 text-[10px] text-ink-500">
        Self-improvement != self-execution: research proposes; nothing here promotes a strategy version or touches
        live trading state without a human decision below.
      </p>

      {report.pending_approvals.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">
            Pending Human Approvals ({report.pending_approvals.length})
          </p>
          <div className="space-y-1.5">
            {report.pending_approvals.map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded border border-base-700 bg-base-900 p-2">
                <div className="text-xs">
                  <span className="text-ink-100">
                    {a.entity_type} #{a.entity_id}
                  </span>
                  <span className="ml-2 text-ink-500">
                    action: {a.action} · {timeAgo(a.created_at)}
                  </span>
                </div>
                <ApprovalDecisionButtons approvalId={a.id} entityType={a.entity_type} action={a.action} />
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Active Hypotheses</p>
      {report.active_hypotheses.length > 0 ? (
        <div className="mb-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-ink-500">
                <th className="pb-2 pr-3 font-normal">Title</th>
                <th className="pb-2 pr-3 font-normal">Source</th>
                <th className="pb-2 pr-3 font-normal">Risk</th>
                <th className="pb-2 pr-3 font-normal">Priority</th>
                <th className="pb-2 font-normal">Status</th>
              </tr>
            </thead>
            <tbody>
              {report.active_hypotheses.map((h) => (
                <tr key={h.id} className="border-t border-base-700/60">
                  <td className="py-1.5 pr-3 text-ink-100">{h.title}</td>
                  <td className="py-1.5 pr-3 text-ink-500">{h.source}</td>
                  <td className="py-1.5 pr-3 text-ink-500">{h.risk}</td>
                  <td className="py-1.5 pr-3 text-ink-300">{h.priority_score?.toFixed(0) ?? "—"}</td>
                  <td className="py-1.5 text-ink-500">{h.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mb-4 text-xs text-ink-500">No open hypotheses — no trigger has proposed one yet.</p>
      )}

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Recent Experiments</p>
      {report.recent_experiments.length > 0 ? (
        <div className="mb-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-ink-500">
                <th className="pb-2 pr-3 font-normal">Strategy</th>
                <th className="pb-2 pr-3 font-normal">Type</th>
                <th className="pb-2 pr-3 font-normal">Changed Params</th>
                <th className="pb-2 pr-3 font-normal">Status</th>
                <th className="pb-2 font-normal">When</th>
              </tr>
            </thead>
            <tbody>
              {report.recent_experiments.map((e) => (
                <tr key={e.id} className="border-t border-base-700/60">
                  <td className="py-1.5 pr-3 text-ink-100">{e.strategy_code ?? "—"}</td>
                  <td className="py-1.5 pr-3 text-ink-500">{e.type}</td>
                  <td className="py-1.5 pr-3 text-ink-500">{e.changed_params?.join(", ") || "—"}</td>
                  <td className={`py-1.5 pr-3 uppercase ${EXPERIMENT_STATUS_COLOR[e.status] ?? "text-ink-500"}`}>{e.status}</td>
                  <td className="py-1.5 text-ink-500">{timeAgo(e.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mb-4 text-xs text-ink-500">No experiments run yet.</p>
      )}

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Strategy Versions</p>
      {report.strategy_versions.length > 0 ? (
        <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          {report.strategy_versions.map((v) => (
            <div key={v.id} className="rounded-lg border border-base-700 bg-base-900 p-2">
              <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">
                {v.strategy_code ?? "?"} {v.version}
              </p>
              <p className={`text-xs uppercase ${LIFECYCLE_COLOR[v.lifecycle_status] ?? "text-ink-500"}`}>{v.lifecycle_status}</p>
              <p className="mt-1 text-[10px] text-ink-500">{v.validation_status}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mb-4 text-xs text-ink-500">No strategy versions proposed yet.</p>
      )}

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Degradation &amp; Drift Alerts</p>
      {report.degradation_and_drift_alerts.length > 0 ? (
        <ul className="mb-4 space-y-1">
          {report.degradation_and_drift_alerts.map((d, i) => (
            <li key={i} className={`text-xs ${SEVERITY_COLOR[d.severity] ?? "text-ink-500"}`}>
              ⚠ {d.drift_type} drift on {d.entity} (severity {d.severity}) — {timeAgo(d.ts)}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mb-4 text-xs text-ink-500">No drift detected in recent checks.</p>
      )}

      <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Feature Research</p>
          <p className="mb-1 text-xs text-ink-500">
            {report.feature_research_findings.pattern_signals_with_evidence} pattern signals with evidence ·{" "}
            {report.feature_research_findings.regime_dependent_signals} regime-dependent
          </p>
          {report.feature_research_findings.top_signals.length > 0 ? (
            <ul className="space-y-1">
              {report.feature_research_findings.top_signals.map((sig, i) => (
                <li key={i} className="text-xs text-ink-300">
                  {sig.pattern_type} in {sig.regime}: {sig.expectancy?.toFixed(3) ?? "—"}R (n={sig.sample_size})
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">No pattern signals with enough evidence yet.</p>
          )}
        </div>

        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Knowledge Graph</p>
          {report.knowledge_graph_highlights.length > 0 ? (
            <ul className="space-y-1">
              {report.knowledge_graph_highlights.map((e, i) => (
                <li key={i} className="text-xs text-ink-300">
                  {e.subject} {e.relation} {e.object} ({(e.confidence * 100).toFixed(0)}%, n={e.sample_size})
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">No knowledge-graph edges recorded yet.</p>
          )}
        </div>
      </div>

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Research Budget (24h)</p>
      <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4">
        {budgetEntries.map(([resourceType, b]) => (
          <div key={resourceType} className="rounded-lg border border-base-700 bg-base-900 p-2">
            <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">{resourceType}</p>
            <p className={`text-xs ${b.exhausted ? "text-signal-red" : "text-ink-100"}`}>
              {b.used.toFixed(0)} / {b.limit.toFixed(0)}
            </p>
          </div>
        ))}
      </div>

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Recommendations</p>
      <ul className="mb-1 space-y-1">
        {report.recommendations.map((r, i) => (
          <li key={i} className="text-xs text-ink-300">
            → {r}
          </li>
        ))}
      </ul>
    </section>
  );
}
