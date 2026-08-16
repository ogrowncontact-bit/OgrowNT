import { FUNNEL_STAGES, getConsentSummary, getFunnelSummary, getRecentOrders, getRevenueSummary } from "@/lib/admin/analyticsReader";
import { ReengagementRunner } from "@/components/admin/ReengagementRunner";

function formatMoney(cents: number, currency = "EUR") {
  return new Intl.NumberFormat("en-IE", { style: "currency", currency }).format(cents / 100);
}

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";

export default async function AdminAnalyticsPage() {
  const [funnel, orders, revenue, consent] = await Promise.all([
    getFunnelSummary(),
    getRecentOrders(50),
    getRevenueSummary(),
    getConsentSummary(),
  ]);

  return (
    <div>
      <h1 className="font-display mb-6 text-[24px] text-[var(--inner-ink)]">Analytics</h1>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className={cardLabel}>Revenue (paid)</p>
          <p className={cardValue}>{formatMoney(revenue.totalPaidCents)}</p>
          <p className={cardLabel}>{revenue.paidCount} orders</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Refunded</p>
          <p className={cardValue}>{formatMoney(revenue.refundedCents)}</p>
          <p className={cardLabel}>{revenue.refundedCount} refunds</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Marketing consent</p>
          <p className={cardValue}>{consent.totalConsented}</p>
          <p className={cardLabel}>{consent.totalDeclined} declined</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Unsubscribed</p>
          <p className={cardValue}>{consent.totalUnsubscribed}</p>
        </div>
      </div>

      <ReengagementRunner />

      <h2 className="font-display mb-3 text-[18px] text-[var(--inner-ink)]">Funnel by experience</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Event counts only — no answer content is ever included here.
      </p>
      <div className="mb-8 overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Experience</th>
              {FUNNEL_STAGES.map((stage) => (
                <th key={stage.key} className="whitespace-nowrap px-4 py-3 font-medium">
                  {stage.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {funnel.map((row) => {
              const top = row.counts.landing_view ?? 0;
              return (
                <tr key={row.assessmentId} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">/{row.slug}</td>
                  {FUNNEL_STAGES.map((stage) => {
                    const count = row.counts[stage.key] ?? 0;
                    const pct = top > 0 ? Math.round((count / top) * 100) : null;
                    return (
                      <td key={stage.key} className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                        {count}
                        {pct !== null && stage.key !== "landing_view" && (
                          <span className="ml-1 text-[11px] text-[var(--inner-muted)]">({pct}%)</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h2 className="font-display mb-3 text-[18px] text-[var(--inner-ink)]">Recent orders</h2>
      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Customer</th>
              <th className="px-4 py-3 font-medium">Experience</th>
              <th className="px-4 py-3 font-medium">Product</th>
              <th className="px-4 py-3 font-medium">Amount</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No orders yet.
                </td>
              </tr>
            )}
            {orders.map((o) => (
              <tr key={o.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(o.createdAt)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{o.email}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{o.assessmentName}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{o.productType}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink)]">{formatMoney(o.amountCents, o.currency)}</td>
                <td className="whitespace-nowrap px-4 py-3">
                  <span
                    className={
                      o.status === "paid"
                        ? "text-[var(--inner-accent)]"
                        : o.status === "refunded" || o.status === "failed"
                          ? "text-[var(--inner-muted)]"
                          : "text-[var(--inner-ink-soft)]"
                    }
                  >
                    {o.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
