import Link from "next/link";
import { listRecommendationsForAdmin } from "@/lib/admin/recommendationsReader";

export const dynamic = "force-dynamic";

export default async function AdminRecommendationsPage() {
  const rules = await listRecommendationsForAdmin();

  const bySource = new Map<string, typeof rules>();
  for (const rule of rules) {
    const list = bySource.get(rule.fromSlug) ?? [];
    list.push(rule);
    bySource.set(rule.fromSlug, list);
  }

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Recommendations</h1>
      <p className="mb-6 text-[13px] text-[var(--inner-ink-soft)]">
        The full discovery graph across every experience. Edit weights, conditions, and bridge copy from each source
        experience's editor — this page is a read-only overview.
      </p>

      <div className="space-y-6">
        {[...bySource.entries()].map(([slug, edges]) => (
          <div key={slug} className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
            <div className="flex items-center justify-between border-b border-[var(--inner-line)] px-4 py-3">
              <h2 className="font-display text-[15px] text-[var(--inner-ink)]">
                /{slug} <span className="text-[var(--inner-muted)]">({edges[0]?.fromName})</span>
              </h2>
              <Link
                href={`/admin/assessments/${edges[0]?.fromAssessmentId}`}
                className="text-[12px] text-[var(--inner-accent)] underline underline-offset-2"
              >
                Edit
              </Link>
            </div>
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                  <th className="whitespace-nowrap px-4 py-3 font-medium">Recommends</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">Weight</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">Condition</th>
                  <th className="px-4 py-3 font-medium">Bridge copy</th>
                </tr>
              </thead>
              <tbody>
                {edges.map((e, i) => (
                  <tr key={`${e.fromSlug}-${e.toSlug}-${i}`} className="border-b border-[var(--inner-line)] last:border-0">
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">/{e.toSlug}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{e.weight}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{e.conditionSummary}</td>
                    <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{e.bridgeCopy}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
        {bySource.size === 0 && (
          <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-6 text-center text-[var(--inner-muted)]">
            No recommendation edges configured yet.
          </div>
        )}
      </div>
    </div>
  );
}
