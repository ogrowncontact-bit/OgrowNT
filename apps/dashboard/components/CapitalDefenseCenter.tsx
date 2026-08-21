import type { AdvancedRisk, CircuitBreaker, Concentration, KillSwitchState } from "@/lib/api";
import { RecoveryButton } from "@/components/RecoveryButton";

// Capital Defense Center — "PROMPT 12" §1-15/§61-69/§107-108: the
// AdvancedRiskEngine's own dashboard surface. Deliberately does NOT
// duplicate the existing Risk Center (per-signal RiskDecision audit trail,
// safety_belt_level, per-trade limits) — this covers only what's genuinely
// new this phase: the portfolio-wide RiskScore/RiskState composite, the 6
// named circuit breakers, correlation concentration/hidden factor
// exposure, and the Emergency Kill Switch's richer 4-state recovery
// workflow. RiskScore is explicitly NOT a probability of loss (see the
// note below the badge) — a composite indicator of risk conditions, same
// distinction Opportunity Score already makes for trade quality.

const RISK_STATE_COLOR: Record<string, string> = {
  normal: "text-signal-green",
  caution: "text-signal-yellow",
  defensive: "text-signal-yellow",
  high_risk: "text-signal-red",
  critical: "text-signal-red",
  emergency: "text-signal-red",
  halted: "text-signal-red",
};

const KILL_SWITCH_STATE_COLOR: Record<string, string> = {
  armed: "text-signal-green",
  triggered: "text-signal-red",
  locked: "text-signal-red",
  recovery: "text-signal-yellow",
};

function stateColor(state: string | null): string {
  if (!state) return "text-ink-500";
  return RISK_STATE_COLOR[state] ?? "text-ink-500";
}

function scoreColor(score: number): string {
  if (score >= 60) return "text-signal-red";
  if (score >= 30) return "text-signal-yellow";
  return "text-signal-green";
}

export function CapitalDefenseCenter({
  advancedRisk,
  breakers,
  concentration,
  killSwitchState,
}: {
  advancedRisk: AdvancedRisk | null;
  breakers: CircuitBreaker[] | null;
  concentration: Concentration | null;
  killSwitchState: KillSwitchState | null;
}) {
  const trippedCount = (breakers ?? []).filter((b) => b.tripped).length;

  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-wider text-ink-500">Capital Defense Center</p>
        {advancedRisk && (
          <span className={`text-xs uppercase ${stateColor(advancedRisk.risk_state)}`}>
            {advancedRisk.risk_state.replace("_", " ")}
          </span>
        )}
      </div>
      <p className="mb-4 text-[10px] text-ink-500">
        RiskScore is a composite indicator of risk conditions, not a probability of loss. Advanced Risk Engine
        results feed the sovereign per-signal Risk Engine as an additional gate — they never bypass it.
      </p>

      {advancedRisk ? (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="rounded-lg border border-base-700 bg-base-900 p-3">
              <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Risk Score</p>
              <p className={`text-lg font-semibold ${scoreColor(advancedRisk.risk_score)}`}>
                {advancedRisk.risk_score.toFixed(0)}
              </p>
            </div>
            <div className="rounded-lg border border-base-700 bg-base-900 p-3">
              <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Drawdown</p>
              <p className="text-lg font-semibold text-ink-100">
                {advancedRisk.drawdown_pct !== null ? `${advancedRisk.drawdown_pct.toFixed(1)}%` : "—"}
              </p>
              {advancedRisk.drawdown_level !== null && advancedRisk.drawdown_level > 0 && (
                <p className="text-[10px] text-signal-yellow">DD_LEVEL_{advancedRisk.drawdown_level}</p>
              )}
            </div>
            <div className="rounded-lg border border-base-700 bg-base-900 p-3">
              <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Capital Preservation</p>
              <p className={`text-lg font-semibold ${advancedRisk.capital_preservation_mode ? "text-signal-yellow" : "text-signal-green"}`}>
                {advancedRisk.capital_preservation_mode ? "ACTIVE" : "off"}
              </p>
            </div>
            <div className="rounded-lg border border-base-700 bg-base-900 p-3">
              <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Zero Trade Mode</p>
              <p className={`text-lg font-semibold ${advancedRisk.zero_trade_mode ? "text-signal-red" : "text-signal-green"}`}>
                {advancedRisk.zero_trade_mode ? "ACTIVE" : "off"}
              </p>
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-3 text-[10px]">
            <span className={stateColor(advancedRisk.drawdown_state)}>drawdown: {advancedRisk.drawdown_state ?? "—"}</span>
            <span className={stateColor(advancedRisk.concentration_state)}>
              concentration: {advancedRisk.concentration_state ?? "—"}
            </span>
            <span className={stateColor(advancedRisk.system_risk_state)}>system: {advancedRisk.system_risk_state ?? "—"}</span>
            <span className={stateColor(advancedRisk.execution_risk_state)}>
              execution: {advancedRisk.execution_risk_state ?? "—"}
            </span>
            <span className={stateColor(advancedRisk.model_risk_state)}>model: {advancedRisk.model_risk_state ?? "—"}</span>
            <span className={stateColor(advancedRisk.data_risk_state)}>data: {advancedRisk.data_risk_state ?? "—"}</span>
          </div>

          {advancedRisk.reasons.length > 0 && (
            <ul className="mb-4 space-y-0.5">
              {advancedRisk.reasons.slice(0, 6).map((r, i) => (
                <li key={i} className="text-xs text-ink-300">
                  · {r}
                </li>
              ))}
            </ul>
          )}
          {advancedRisk.degraded && (
            <p className="mb-4 text-xs text-signal-red">
              One or more risk dimensions failed to compute this cycle — failed closed to the most conservative
              reading rather than being silently skipped.
            </p>
          )}
        </>
      ) : (
        <p className="mb-4 text-xs text-ink-500">Advanced risk assessment unavailable.</p>
      )}

      <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">
            Circuit Breakers {breakers ? `(${trippedCount} tripped)` : ""}
          </p>
          {breakers && breakers.length > 0 ? (
            <div className="grid grid-cols-2 gap-2">
              {breakers.map((b) => (
                <div
                  key={b.name}
                  className={`rounded-lg border p-2 ${b.tripped ? "border-signal-red/40" : "border-base-700"}`}
                >
                  <p className="text-[10px] uppercase tracking-wider text-ink-500">{b.name}</p>
                  <p className={`text-xs uppercase ${b.tripped ? "text-signal-red" : "text-signal-green"}`}>
                    {b.tripped ? "tripped" : "armed"}
                  </p>
                  {b.reason && <p className="mt-1 text-[10px] text-ink-500">{b.reason}</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-ink-500">Breaker status unavailable.</p>
          )}
        </div>

        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Concentration</p>
          {concentration ? (
            <div>
              <p className={`text-xs uppercase ${stateColor(concentration.concentration_state)}`}>
                {concentration.concentration_state} · max cluster {concentration.max_cluster_exposure_pct.toFixed(1)}% of
                equity
              </p>
              {concentration.hidden_factor_warnings.length > 0 ? (
                <ul className="mt-2 space-y-0.5">
                  {concentration.hidden_factor_warnings.slice(0, 4).map((w, i) => (
                    <li key={i} className="text-xs text-signal-yellow">
                      · {w}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-xs text-ink-500">No hidden-factor concentration warnings.</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-ink-500">Concentration data unavailable.</p>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between rounded-lg border border-base-700 bg-base-900 p-3">
        <div>
          <p className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Emergency Kill Switch</p>
          {killSwitchState ? (
            <p className={`text-sm uppercase ${KILL_SWITCH_STATE_COLOR[killSwitchState.kill_switch_state] ?? "text-ink-500"}`}>
              {killSwitchState.kill_switch_state}
            </p>
          ) : (
            <p className="text-sm text-ink-500">unavailable</p>
          )}
        </div>
        {killSwitchState && <RecoveryButton killSwitchState={killSwitchState.kill_switch_state} />}
      </div>
    </section>
  );
}
