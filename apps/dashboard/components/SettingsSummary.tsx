import type { Broker, HealthResponse, RiskState, SystemStatus } from "@/lib/api";

// risk_limits.yaml's sections aren't uniformly flat (e.g. drawdown_levels'
// entries are themselves {threshold_pct, response} objects) even though
// RiskState.limits' own TS type says Record<string, Record<string,
// number>> — this renders whatever shape actually comes back rather than
// crashing React on a nested object child.
function renderLimitValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

// Configuration Center — "PROMPT 14" §96-97. §97: "Configurações críticas
// devem aparecer READ-ONLY até futura aprovação manual" — this page is
// deliberately entirely read-only end to end: it has no form, no submit
// button, no mutation call anywhere in this file. Editing risk limits
// still only happens through the existing, audited
// PATCH /api/system/risk-limits flow (packages/risk/config_version.py) —
// nothing here bypasses or duplicates it.
export function SettingsSummary({
  riskState,
  brokers,
  health,
  systemStatus,
}: {
  riskState: RiskState | null;
  brokers: Broker[] | null;
  health: HealthResponse | null;
  systemStatus: SystemStatus | null;
}) {
  return (
    <div>
      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-500">Protected Settings — read-only</p>
        <p className="mb-3 text-[10px] text-ink-500">
          Risk floors, drawdown limits, the kill switch, and live-trading permissions cannot be changed from this
          page — only via the audited, versioned risk-config flow (Risk Center).
        </p>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          <div className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
            <p className="text-ink-500">Safety belt</p>
            <p className="text-ink-100">{systemStatus?.safety_belt_level ?? "—"}</p>
          </div>
          <div className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
            <p className="text-ink-500">Trading enabled</p>
            <p className={systemStatus?.trading_enabled ? "text-signal-green" : "text-signal-red"}>
              {systemStatus?.trading_enabled ? "yes" : "no"}
            </p>
          </div>
          <div className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
            <p className="text-ink-500">Live trading</p>
            <p className="text-signal-green">disabled (structural)</p>
          </div>
        </div>
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Risk Limits</p>
        {riskState && Object.keys(riskState.limits).length > 0 ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {Object.entries(riskState.limits).map(([section, values]) => (
              <div key={section} className="rounded border border-base-700/60 p-2.5">
                <p className="mb-1 text-[10px] uppercase text-ink-500">{section}</p>
                {Object.entries(values).map(([k, v]) => (
                  <p key={k} className="text-[11px] text-ink-300">
                    {k}: <span className="text-ink-100">{renderLimitValue(v)}</span>
                  </p>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">Risk limits unavailable.</p>
        )}
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Data &amp; Broker Providers</p>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {health?.components.map((c) => (
            <div key={c.name} className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
              <span className="text-ink-300">{c.name}</span> <span className="text-ink-500">{c.detail ?? c.status}</span>
            </div>
          ))}
          {brokers?.map((b) => (
            <div key={b.id} className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
              <span className="text-ink-300">broker: {b.name}</span> <span className="text-ink-500">({b.kind})</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
