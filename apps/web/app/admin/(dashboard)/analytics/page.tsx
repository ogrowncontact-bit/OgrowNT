import Link from "next/link";
import {
  FUNNEL_STAGES,
  getAiCallStats,
  getConsentSummary,
  getDeletionRequests,
  getFunnelSummary,
  getQuestionDropoff,
  getRecentAiFailures,
  getRecentOrders,
  getRevenueSummary,
} from "@/lib/admin/analyticsReader";
import { ReengagementRunner } from "@/components/admin/ReengagementRunner";
import { RefundButton } from "@/components/admin/RefundButton";

function formatMoney(cents: number, currency = "EUR") {
  return new Intl.NumberFormat("en-IE", { style: "currency", currency }).format(cents / 100);
}

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";

export default async function AdminAnalyticsPage({ searchParams }: { searchParams: Promise<{ assessmentId?: string }> }) {
  const { assessmentId: requestedAssessmentId } = await searchParams;
  const [funnel, orders, revenue, consent, deletionRequests, aiStats, aiFailures] = await Promise.all([
    getFunnelSummary(),
    getRecentOrders(50),
    getRevenueSummary(),
    getConsentSummary(),
    getDeletionRequests(),
    getAiCallStats(),
    getRecentAiFailures(10),
  ]);

  const selectedAssessmentId = requestedAssessmentId ?? funnel[0]?.assessmentId;
  const dropoff = selectedAssessmentId ? await getQuestionDropoff(selectedAssessmentId) : null;

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

      <h2 className="font-display mb-3 text-[18px] text-[var(--inner-ink)]">Drop-off by question</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Core questions only, in order — where people stop within one experience's fixed backbone.
      </p>
      <div className="mb-3 flex flex-wrap gap-2">
        {funnel.map((row) => (
          <Link
            key={row.assessmentId}
            href={`/admin/analytics?assessmentId=${row.assessmentId}`}
            className={
              row.assessmentId === selectedAssessmentId
                ? "rounded-[var(--inner-radius-sm)] bg-[var(--inner-accent)] px-3 py-1.5 text-[13px] font-medium text-[var(--inner-accent-contrast)]"
                : "rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[13px] text-[var(--inner-ink-soft)] hover:border-[var(--inner-accent-soft)]"
            }
          >
            /{row.slug}
          </Link>
        ))}
      </div>
      <div className="mb-8 overflow-hidden rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        {!dropoff || dropoff.questions.length === 0 ? (
          <p className="px-4 py-6 text-center text-[13px] text-[var(--inner-muted)]">
            No published core questions for this experience yet.
          </p>
        ) : (
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                <th className="px-4 py-3 font-medium">#</th>
                <th className="px-4 py-3 font-medium">Question</th>
                <th className="px-4 py-3 font-medium">Answered</th>
              </tr>
            </thead>
            <tbody>
              {dropoff.questions.map((q, i) => (
                <tr key={q.key} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="px-4 py-3 text-[var(--inner-muted)]">{i + 1}</td>
                  <td className="px-4 py-3 text-[var(--inner-ink)]">{q.prompt}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                    {q.answered} / {dropoff.totalStarted}
                    <span className="ml-1 text-[11px] text-[var(--inner-muted)]">({q.pctOfStarted}%)</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-[18px] text-[var(--inner-ink)]">Recent orders</h2>
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
              <th className="px-4 py-3 font-medium">Experience</th>
              <th className="px-4 py-3 font-medium">Product</th>
              <th className="px-4 py-3 font-medium">Amount</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-[var(--inner-muted)]">
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
                <td className="whitespace-nowrap px-4 py-3">
                  {o.status === "paid" && <RefundButton orderId={o.id} amountLabel={formatMoney(o.amountCents, o.currency)} />}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="font-display mb-3 mt-8 text-[18px] text-[var(--inner-ink)]">AI cost &amp; latency</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Every Question/Response/Profile/Report/Recommendation AI call, whether or not it succeeded — a "0 ok" module
        with calls logged usually means ANTHROPIC_API_KEY isn't set and the deterministic fallback is doing the work.
      </p>
      <div className="mb-4 overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="px-4 py-3 font-medium">Module</th>
              <th className="px-4 py-3 font-medium">Calls</th>
              <th className="px-4 py-3 font-medium">Ok rate</th>
              <th className="px-4 py-3 font-medium">Avg latency</th>
              <th className="px-4 py-3 font-medium">Input tokens</th>
              <th className="px-4 py-3 font-medium">Output tokens</th>
            </tr>
          </thead>
          <tbody>
            {aiStats.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No AI calls logged yet.
                </td>
              </tr>
            )}
            {aiStats.map((s) => (
              <tr key={s.module} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="px-4 py-3 font-medium text-[var(--inner-ink)]">{s.module}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{s.totalCalls}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">
                  {s.okCalls} / {s.totalCalls} ({s.totalCalls > 0 ? Math.round((s.okCalls / s.totalCalls) * 100) : 0}%)
                </td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{s.avgLatencyMs}ms</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{s.totalInputTokens.toLocaleString()}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{s.totalOutputTokens.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {aiFailures.length > 0 && (
        <div className="mb-8 overflow-hidden rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                <th className="px-4 py-3 font-medium">Recent failures</th>
                <th className="px-4 py-3 font-medium">Module</th>
                <th className="px-4 py-3 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {aiFailures.map((f) => (
                <tr key={f.id} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{f.errorReason ?? "Unknown error"}</td>
                  <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{f.module}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(f.occurredAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="font-display mb-3 text-[18px] text-[var(--inner-ink)]">GDPR erasure requests</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Self-serve deletions from /privacy — audit trail only, the email is already anonymized by the time it lands
        here.
      </p>
      <div className="overflow-hidden rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="px-4 py-3 font-medium">Requested</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Completed</th>
            </tr>
          </thead>
          <tbody>
            {deletionRequests.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No erasure requests yet.
                </td>
              </tr>
            )}
            {deletionRequests.map((r) => (
              <tr key={r.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(r.requestedAt)}</td>
                <td className="px-4 py-3 text-[var(--inner-ink)]">{r.status}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                  {r.completedAt ? formatDate(r.completedAt) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
