import { EXPERIMENTS } from "@/lib/experiments";
import { getExperimentResults } from "@/lib/admin/experimentsReader";

export const dynamic = "force-dynamic";

export default async function AdminExperimentsPage() {
  const results = await getExperimentResults();
  const resultsByExperiment = new Map<string, typeof results>();
  for (const r of results) {
    const list = resultsByExperiment.get(r.experimentId) ?? [];
    list.push(r);
    resultsByExperiment.set(r.experimentId, list);
  }
  // Results can reference an experiment id no longer in EXPERIMENTS (removed after the test ended) — surface those too.
  const allExperimentIds = new Set([...EXPERIMENTS.map((e) => e.id), ...resultsByExperiment.keys()]);

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Experiments</h1>
      <p className="mb-6 text-[13px] text-[var(--inner-ink-soft)]">
        Deterministic A/B assignment (see lib/experiments.ts) — variant is stable per visitor, no DB write needed to assign it.
        &quot;Converted&quot; means the visitor went on to complete a purchase.
      </p>

      {allExperimentIds.size === 0 && (
        <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-6 text-[14px] text-[var(--inner-ink-soft)]">
          No experiments configured. Add an entry to EXPERIMENTS in lib/experiments.ts when there&apos;s a specific test to run —
          this deliberately isn&apos;t pre-populated with invented tests.
        </div>
      )}

      <div className="space-y-6">
        {[...allExperimentIds].map((id) => {
          const definition = EXPERIMENTS.find((e) => e.id === id);
          const variantResults = resultsByExperiment.get(id) ?? [];
          const totalExposed = variantResults.reduce((sum, r) => sum + r.exposed, 0);
          return (
            <div key={id} className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
              <div className="mb-3 flex items-center justify-between">
                <p className="font-display text-[16px] text-[var(--inner-ink)]">{id}</p>
                <span className={`text-[12px] ${definition ? "text-[var(--inner-accent)]" : "text-[var(--inner-muted)]"}`}>
                  {definition ? "Configured" : "Removed from config (historical results only)"}
                </span>
              </div>
              {definition && <p className="mb-3 text-[12px] text-[var(--inner-muted)]">Variants: {definition.variants.join(", ")}</p>}
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                    <th className="py-2 font-medium">Variant</th>
                    <th className="py-2 font-medium">Exposed</th>
                    <th className="py-2 font-medium">Converted</th>
                    <th className="py-2 font-medium">Conversion</th>
                    <th className="py-2 font-medium">Traffic share</th>
                  </tr>
                </thead>
                <tbody>
                  {variantResults.map((r) => (
                    <tr key={r.variant} className="border-b border-[var(--inner-line)] last:border-0">
                      <td className="py-2 font-medium text-[var(--inner-ink)]">{r.variant}</td>
                      <td className="py-2 text-[var(--inner-ink-soft)]">{r.exposed}</td>
                      <td className="py-2 text-[var(--inner-ink-soft)]">{r.converted}</td>
                      <td className="py-2 text-[var(--inner-ink-soft)]">{r.conversionPct}%</td>
                      <td className="py-2 text-[var(--inner-ink-soft)]">
                        {totalExposed > 0 ? Math.round((r.exposed / totalExposed) * 1000) / 10 : 0}%
                      </td>
                    </tr>
                  ))}
                  {variantResults.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-3 text-center text-[var(--inner-muted)]">
                        No exposures recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </div>
  );
}
