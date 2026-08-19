import Link from "next/link";
import { listOrdersForAdmin } from "@/lib/admin/ordersReader";
import { formatPrice } from "@/lib/money";
import { RefundButton } from "@/components/admin/RefundButton";
import { CheckStatusButton } from "@/components/admin/CheckStatusButton";

function formatDate(d: Date | null) {
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const STATUS_COLOR: Record<string, string> = {
  paid: "text-[var(--inner-accent)]",
  pending: "text-[var(--inner-ink-soft)]",
  refunded: "text-[var(--inner-muted)]",
  partially_refunded: "text-[var(--inner-muted)]",
  failed: "text-[var(--inner-muted)]",
  cancelled: "text-[var(--inner-muted)]",
};

export const dynamic = "force-dynamic";

export default async function AdminOrdersPage() {
  const orders = await listOrdersForAdmin(100);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-[24px] text-[var(--inner-ink)]">Orders</h1>
        <a
          href="/api/admin/exports/orders"
          className="rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[13px] text-[var(--inner-ink-soft)] hover:border-[var(--inner-accent-soft)]"
        >
          Export CSV
        </a>
      </div>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Customer</th>
              <th className="px-4 py-3 font-medium">Product</th>
              <th className="px-4 py-3 font-medium">Amount</th>
              <th className="px-4 py-3 font-medium">Provider</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Paid</th>
              <th className="px-4 py-3 font-medium">Report</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No orders yet.
                </td>
              </tr>
            )}
            {orders.map((o) => {
              const remainingCents = o.amountCents - o.refundedCents;
              const refundable = (o.status === "paid" || o.status === "partially_refunded") && remainingCents > 0;
              return (
                <tr key={o.id} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(o.createdAt)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{o.email}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                    {o.assessmentName} · {o.productType}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink)]">
                    {formatPrice(o.amountCents, o.currency)}
                    {o.refundedCents > 0 && (
                      <span className="ml-1 text-[11px] text-[var(--inner-muted)]">
                        (−{formatPrice(o.refundedCents, o.currency)})
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{o.provider}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className={STATUS_COLOR[o.status] ?? "text-[var(--inner-ink-soft)]"}>{o.status}</span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(o.paidAt)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{o.reportStatus ?? "—"}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    {refundable && <RefundButton orderId={o.id} remainingCents={remainingCents} currency={o.currency} />}
                    {o.status === "pending" && <CheckStatusButton orderId={o.id} />}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-[13px] text-[var(--inner-ink-soft)]">
        <Link href="/admin/reports" className="underline underline-offset-2">
          Report generation/delivery failures →
        </Link>
      </p>
    </div>
  );
}
