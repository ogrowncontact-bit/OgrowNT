import { cookies } from "next/headers";
import { getDashboardOpportunities } from "@/lib/api";
import { OpportunityRadar } from "@/components/OpportunityRadar";

export const dynamic = "force-dynamic";

export default async function OpportunitiesPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const data = await getDashboardOpportunities(token);

  return (
    <div>
      <OpportunityRadar opportunities={data?.opportunities ?? []} />
      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
          Correlated Opportunity Clusters {data ? `(${data.clusters.length})` : ""}
        </p>
        {data && data.clusters.length > 0 ? (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {data.clusters.map((c, i) => (
              <div key={i} className="rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
                <p className="text-ink-100">{c.factor ?? "cluster"}</p>
                <p className="text-ink-500">{c.asset_ids.length} correlated asset(s)</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No correlated clusters detected right now.</p>
        )}
      </section>
      <section className="rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
          Dynamic Watchlist {data ? `(${data.watchlist.length})` : ""}
        </p>
        {data && data.watchlist.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {data.watchlist.map((w) => (
              <span key={w.id} className="flex items-center gap-1.5 rounded border border-base-700/60 px-2 py-1 text-xs">
                asset #{w.asset_id} <span className="text-ink-500">({w.reason})</span>
              </span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">Watchlist is empty.</p>
        )}
      </section>
    </div>
  );
}
