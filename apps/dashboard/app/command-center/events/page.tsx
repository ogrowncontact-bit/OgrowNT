import { cookies } from "next/headers";
import { getDashboardEvents } from "@/lib/api";
import { LiveActivityFeed } from "@/components/LiveActivityFeed";

export const dynamic = "force-dynamic";

function daysUntil(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms < 0) return "past";
  const days = ms / 86_400_000;
  if (days < 1) return `in ${Math.round(ms / 3_600_000)}h`;
  return `in ${Math.round(days)}d`;
}

const IMPORTANCE_COLOR: Record<string, string> = {
  low: "text-ink-500",
  medium: "text-signal-yellow",
  high: "text-signal-orange",
  critical: "text-signal-red",
};

export default async function EventsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const data = await getDashboardEvents(token);

  return (
    <div>
      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Economic Calendar (Event Countdown)</p>
        {data && data.macro_events.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-ink-500">
                  <th className="pb-2 pr-3 font-normal">Event</th>
                  <th className="pb-2 pr-3 font-normal">Country</th>
                  <th className="pb-2 pr-3 font-normal">When</th>
                  <th className="pb-2 font-normal">Importance</th>
                </tr>
              </thead>
              <tbody>
                {data.macro_events.map((m) => (
                  <tr key={m.id} className="border-t border-base-700/60">
                    <td className="py-1.5 pr-3 text-ink-100">{m.event}</td>
                    <td className="py-1.5 pr-3 text-ink-500">{m.country}</td>
                    <td className="py-1.5 pr-3 text-ink-300">{daysUntil(m.scheduled_at)}</td>
                    <td className={`py-1.5 ${IMPORTANCE_COLOR[m.importance] ?? "text-ink-500"}`}>{m.importance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-ink-500">No upcoming macro events.</p>
        )}
      </section>

      <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">Market Events</p>
        {data && data.market_events.length > 0 ? (
          <div className="space-y-1">
            {data.market_events.map((e) => (
              <div key={e.id} className="flex items-center justify-between rounded border border-base-700/60 px-2.5 py-1.5 text-xs">
                <span>
                  <span className="text-ink-100">{e.asset_symbol}</span> <span className="text-ink-500">{e.event_type}</span>
                </span>
                <span className="text-ink-500">{new Date(e.ts).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-ink-500">No recent market events.</p>
        )}
      </section>

      <LiveActivityFeed events={data?.activity_feed ?? []} />
    </div>
  );
}
