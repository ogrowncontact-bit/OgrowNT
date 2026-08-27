import { listSupportTickets, getOpenSupportTicketCount } from "@/lib/admin/supportReader";
import { ResolveTicketButton } from "@/components/admin/ResolveTicketButton";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";

const CATEGORY_LABEL: Record<string, string> = {
  payment: "Payment",
  report: "Report",
  email: "Email",
  technical: "Technical",
  content: "Content",
};

export const dynamic = "force-dynamic";

/** FASE 33 §SUPPORT — issue reports, distinct from the "resend my report" self-serve flow. No answer content is ever collected or shown here. */
export default async function AdminSupportPage() {
  const [openCount, tickets] = await Promise.all([getOpenSupportTicketCount(), listSupportTickets()]);

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Support</h1>
      <p className="mb-6 max-w-2xl text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">
        Issues reported from /support, categorized by type. Separate from the report-resend flow.
      </p>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className={cardLabel}>Open</p>
          <p className={cardValue}>{openCount}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Total</p>
          <p className={cardValue}>{tickets.length}</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Date</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Category</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Message</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Status</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium" />
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr key={t.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(t.createdAt)}</td>
                <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">{CATEGORY_LABEL[t.category] ?? t.category}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{t.email}</td>
                <td className="max-w-[360px] px-4 py-3 text-[var(--inner-ink-soft)]">{t.message}</td>
                <td className="px-4 py-3">
                  <span className={t.status === "open" ? "text-[var(--inner-accent)]" : "text-[var(--inner-ink-soft)]"}>
                    {t.status === "open" ? "Open" : "Resolved"}
                  </span>
                </td>
                <td className="px-4 py-3">{t.status === "open" && <ResolveTicketButton ticketId={t.id} />}</td>
              </tr>
            ))}
            {tickets.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No support tickets yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
