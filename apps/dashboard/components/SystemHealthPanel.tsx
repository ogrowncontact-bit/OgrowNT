import type { SelfDiagnosticReport, SystemHealthScore } from "@/lib/api";

// System Health / Self Diagnostic — "PROMPT 14" §54-55, §111, §116, §124-129.
// health_score/component_health reuse GET /api/system/health's own
// component checks (packages/system/health_score.py); self_diagnostic runs
// a small set of REAL probes (packages/system/diagnostics.py) — never a
// claim about a subsystem this process can't genuinely reach.
const STATUS_COLOR: Record<string, string> = { green: "text-signal-green", yellow: "text-signal-yellow", red: "text-signal-red" };
const READINESS_COLOR: Record<string, string> = {
  ready: "text-signal-green",
  caution: "text-signal-yellow",
  degraded: "text-signal-orange",
  not_ready: "text-signal-red",
  halted: "text-signal-red",
};

export function SystemHealthPanel({
  componentHealth,
  healthScore,
  diagnostic,
}: {
  componentHealth: Record<string, string>;
  healthScore: SystemHealthScore;
  diagnostic: SelfDiagnosticReport;
}) {
  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">System Health</p>
        <span className={READINESS_COLOR[healthScore.readiness_state] ?? "text-ink-500"}>
          {healthScore.score.toFixed(0)}/100 · {healthScore.readiness_state.replace("_", " ").toUpperCase()}
        </span>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-3">
        {Object.entries(componentHealth).map(([name, status]) => (
          <div key={name} className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
            <span className="text-ink-300">{name.replace(/_/g, " ")}</span>{" "}
            <span className={STATUS_COLOR[status] ?? "text-ink-500"}>{status.toUpperCase()}</span>
          </div>
        ))}
      </div>

      {healthScore.reasons.length > 0 && (
        <div className="mb-4 space-y-0.5">
          {healthScore.reasons.map((r, i) => (
            <p key={i} className="text-[10px] text-signal-yellow">
              · {r}
            </p>
          ))}
        </div>
      )}

      <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">
        Self Diagnostic {diagnostic.ok ? <span className="text-signal-green">OK</span> : <span className="text-signal-red">FAILING</span>}
      </p>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {diagnostic.checks.map((c) => (
          <div key={c.name} className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
            <p>
              <span className="text-ink-300">{c.name}</span>{" "}
              <span className={c.ok ? "text-signal-green" : "text-signal-red"}>{c.ok ? "OK" : "FAIL"}</span>
            </p>
            <p className="mt-0.5 truncate text-[10px] text-ink-500" title={c.detail}>
              {c.detail}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[10px] text-ink-500">ran at {new Date(diagnostic.ran_at).toLocaleString()}</p>
    </section>
  );
}
