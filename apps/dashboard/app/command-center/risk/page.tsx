import { cookies } from "next/headers";
import { getDashboardRisk, getKillSwitchState, getPortfolioExposure } from "@/lib/api";
import { CapitalDefenseCenter } from "@/components/CapitalDefenseCenter";
import { RiskBadge } from "@/components/RiskBadge";
import { RiskHeatmap } from "@/components/RiskHeatmap";

export const dynamic = "force-dynamic";

export default async function RiskPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [data, killSwitchState, exposure] = await Promise.all([
    getDashboardRisk(token),
    getKillSwitchState(token),
    getPortfolioExposure(token),
  ]);

  return (
    <div>
      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[11px] uppercase tracking-wider text-ink-500">Risk State</p>
          {data && <RiskBadge level={data.risk_state.safety_belt_level} />}
        </div>
        <p className="text-xs text-ink-500">
          {data?.risk_state.recent_decisions.length ?? 0} recent risk decisions evaluated.
        </p>
      </section>

      <CapitalDefenseCenter
        advancedRisk={data?.advanced ?? null}
        breakers={data?.breakers ?? null}
        concentration={data?.concentration ?? null}
        killSwitchState={killSwitchState}
      />

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Risk Heatmap</p>
        {exposure ? (
          <RiskHeatmap
            byAsset={exposure.by_asset}
            byStrategy={exposure.by_strategy}
            byDirection={exposure.by_direction}
            correlations={exposure.correlations}
          />
        ) : (
          <p className="text-xs text-ink-500">Exposure data unavailable.</p>
        )}
      </section>

      <section className="rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Recent Risk Decisions</p>
        {data && data.risk_state.recent_decisions.length > 0 ? (
          <div className="space-y-1">
            {data.risk_state.recent_decisions.map((d, i) => (
              <div key={i} className="flex items-center justify-between rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
                <span>
                  <span className="text-ink-100">{d.asset_symbol}</span> <span className="text-ink-500">{d.strategy_code}</span>
                </span>
                <span className={d.approved ? "text-signal-green" : "text-signal-red"}>{d.decision}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No recent risk decisions.</p>
        )}
      </section>
    </div>
  );
}
