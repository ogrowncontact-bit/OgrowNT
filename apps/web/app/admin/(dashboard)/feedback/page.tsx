import { prisma } from "@inner/db";
import { listFeedback, getFeedbackSummary, RATING_LABELS } from "@/lib/admin/feedbackReader";
import type { FeedbackRating } from "@inner/db";

export const dynamic = "force-dynamic";

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";
const selectClass = "rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-paper)] px-3 py-2 text-[13px] text-[var(--inner-ink)]";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

export default async function AdminFeedbackPage({
  searchParams,
}: {
  searchParams: Promise<{ product?: string; rating?: string; language?: string; from?: string; to?: string }>;
}) {
  const { product, rating, language, from, to } = await searchParams;

  const [summary, rows, assessments] = await Promise.all([
    getFeedbackSummary(),
    listFeedback({
      assessmentSlug: product || undefined,
      rating: (rating as FeedbackRating) || undefined,
      language: language || undefined,
      from: from ? new Date(from) : undefined,
      to: to ? new Date(to) : undefined,
    }),
    prisma.assessment.findMany({ select: { slug: true, name: true }, orderBy: { name: "asc" } }),
  ]);

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Feedback</h1>
      <p className="mb-6 max-w-2xl text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">
        Optional, post-report &quot;did this feel accurate?&quot; responses. Never required to see or keep a report,
        never combined with marketing outreach.
      </p>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-6">
        <div className={card}>
          <p className={cardLabel}>Total responses</p>
          <p className={cardValue}>{summary.total}</p>
        </div>
        {(["very_accurate", "mostly_accurate", "somewhat_accurate", "not_very_accurate", "not_accurate"] as FeedbackRating[]).map((r) => (
          <div key={r} className={card}>
            <p className={cardLabel}>{RATING_LABELS[r]}</p>
            <p className={cardValue}>{summary.byRating.find((b) => b.rating === r)?.count ?? 0}</p>
          </div>
        ))}
      </div>

      <form method="get" className="mb-6 flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-[12px] text-[var(--inner-muted)]">Product</label>
          <select name="product" defaultValue={product ?? ""} className={selectClass}>
            <option value="">All</option>
            {assessments.map((a) => (
              <option key={a.slug} value={a.slug}>
                {a.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[var(--inner-muted)]">Rating</label>
          <select name="rating" defaultValue={rating ?? ""} className={selectClass}>
            <option value="">All</option>
            {Object.entries(RATING_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[var(--inner-muted)]">Language</label>
          <select name="language" defaultValue={language ?? ""} className={selectClass}>
            <option value="">All</option>
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="pt">Portuguese</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[var(--inner-muted)]">From</label>
          <input type="date" name="from" defaultValue={from ?? ""} className={selectClass} />
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[var(--inner-muted)]">To</label>
          <input type="date" name="to" defaultValue={to ?? ""} className={selectClass} />
        </div>
        <button type="submit" className="rounded-[var(--inner-radius-sm)] bg-[var(--inner-accent)] px-4 py-2 text-[13px] font-medium text-[var(--inner-accent-contrast)]">
          Filter
        </button>
      </form>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Date</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Product</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Rating</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Language</th>
              <th className="px-4 py-3 font-medium">Comment</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(r.createdAt)}</td>
                <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">{r.assessmentName}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{RATING_LABELS[r.rating]}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{r.language}</td>
                <td className="max-w-[360px] px-4 py-3 text-[var(--inner-ink-soft)]">{r.comment ?? "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No feedback matches these filters yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
