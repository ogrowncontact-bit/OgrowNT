import { cookies } from "next/headers";
import { getDashboardStrategies } from "@/lib/api";
import { LifecycleBadge } from "@/components/LifecycleBadge";
import { StrategyActionButton } from "@/components/StrategyActionButton";

export const dynamic = "force-dynamic";

export default async function StrategiesPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const data = await getDashboardStrategies(token);

  const learningByCode = new Map((data?.learning ?? []).map((l) => [l.strategy_code, l]));

  return (
    <section className="rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
        Strategy Center {data ? `(${data.strategies.length})` : ""}
      </p>
      {data && data.strategies.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wide text-ink-500">
                <th className="pb-2 pr-3 font-normal">Strategy</th>
                <th className="pb-2 pr-3 font-normal">Status</th>
                <th className="pb-2 pr-3 font-normal">Win Rate</th>
                <th className="pb-2 pr-3 font-normal">Expectancy</th>
                <th className="pb-2 pr-3 font-normal">Health</th>
                <th className="pb-2 font-normal">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.strategies.map((s) => {
                const learning = learningByCode.get(s.code);
                return (
                  <tr key={s.id} className="border-t border-base-700/60">
                    <td className="py-1.5 pr-3 text-ink-100">
                      {s.name} <span className="text-ink-500">({s.family} v{s.version})</span>
                    </td>
                    <td className="py-1.5 pr-3">
                      <LifecycleBadge stage={s.lifecycle_stage} />
                    </td>
                    <td className="py-1.5 pr-3 text-ink-300">
                      {learning?.win_rate != null ? `${(learning.win_rate * 100).toFixed(0)}%` : "—"}
                    </td>
                    <td className="py-1.5 pr-3 text-ink-300">{learning?.expectancy?.toFixed(3) ?? "—"}</td>
                    <td className="py-1.5 pr-3 text-ink-300">{learning?.health_score?.toFixed(0) ?? "—"}</td>
                    <td className="py-1.5">
                      {s.lifecycle_stage === "quarantine" && (
                        <StrategyActionButton strategyId={s.id} action="restore" label="Restore" confirmText="Restore this strategy from quarantine?" />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-xs text-ink-500">No strategies registered.</p>
      )}
    </section>
  );
}
