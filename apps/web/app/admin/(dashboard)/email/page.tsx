import { listEmailEventsForAdmin, getEmailStatusCounts } from "@/lib/admin/emailReader";
import { RetryReportButton } from "@/components/admin/RetryReportButton";

function formatDate(d: Date | null) {
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";

const STATUS_COLOR: Record<string, string> = {
  sent: "text-[var(--inner-ink-soft)]",
  delivered: "text-[var(--inner-accent)]",
  bounced: "text-[var(--inner-accent)]",
  failed: "text-[var(--inner-accent)]",
};

export const dynamic = "force-dynamic";

export default async function AdminEmailPage() {
  const [events, counts] = await Promise.all([listEmailEventsForAdmin(150), getEmailStatusCounts()]);

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Email</h1>
      <p className="mb-6 text-[13px] text-[var(--inner-ink-soft)]">
        Every transactional and marketing send this account has made. This is a delivery log, not a composer — there
        is no way to send a new email from here, only to retry one that already failed.
      </p>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className={cardLabel}>Sent</p>
          <p className={cardValue}>{counts.sent}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Delivered</p>
          <p className={cardValue}>{counts.delivered}</p>
          <p className={cardLabel}>where the provider reports it</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Bounced</p>
          <p className={`${cardValue} ${counts.bounced > 0 ? "text-[var(--inner-accent)]" : ""}`}>{counts.bounced}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Failed</p>
          <p className={`${cardValue} ${counts.failed > 0 ? "text-[var(--inner-accent)]" : ""}`}>{counts.failed}</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="px-4 py-3 font-medium">Sent</th>
              <th className="px-4 py-3 font-medium">Recipient</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Delivered</th>
              <th className="px-4 py-3 font-medium">Opened</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {events.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No emails sent yet.
                </td>
              </tr>
            )}
            {events.map((e) => (
              <tr key={e.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(e.sentAt)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{e.email}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                  {e.type}
                  {!e.transactional && <span className="ml-1 text-[11px] text-[var(--inner-muted)]">(marketing)</span>}
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  <span className={STATUS_COLOR[e.status] ?? "text-[var(--inner-ink-soft)]"}>{e.status}</span>
                  {e.failureReason && <p className="text-[11px] text-[var(--inner-muted)]">{e.failureReason}</p>}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(e.deliveredAt)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(e.openedAt)}</td>
                <td className="whitespace-nowrap px-4 py-3">
                  {e.status === "failed" && e.reportId && e.type === "report_delivery" && (
                    <RetryReportButton reportId={e.reportId} kind="email" />
                  )}
                  {e.status === "failed" && e.reportId && e.type === "report_preparing" && (
                    <RetryReportButton reportId={e.reportId} kind="generation" />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
