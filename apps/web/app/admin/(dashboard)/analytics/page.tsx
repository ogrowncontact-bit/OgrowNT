import Link from "next/link";
import {
  FUNNEL_STAGES,
  getAiCallStats,
  getConsentSummary,
  getDeletionRequests,
  getFunnelSummary,
  getQuestionDropoff,
  getRecentAiFailures,
  getRevenueSummary,
} from "@/lib/admin/analyticsReader";
import { getRealQuestionAnalytics } from "@/lib/admin/questionAnalyticsReader";
import { getGlobalSegments, getPerAssessmentSegments } from "@/lib/admin/segmentsReader";
import { getExperimentResults } from "@/lib/admin/experimentsReader";
import { ReengagementRunner } from "@/components/admin/ReengagementRunner";
import { AbandonmentRunner } from "@/components/admin/AbandonmentRunner";
import { formatPrice as formatMoney } from "@/lib/money";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";

export default async function AdminAnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ assessmentId?: string; from?: string; to?: string }>;
}) {
  const { assessmentId: requestedAssessmentId, from, to } = await searchParams;
  const dateRange = {
    from: from ? new Date(`${from}T00:00:00.000Z`) : undefined,
    to: to ? new Date(`${to}T23:59:59.999Z`) : undefined,
  };
  const [funnel, revenue, consent, deletionRequests, aiStats, aiFailures, globalSegments, perAssessmentSegments, experimentResults] =
    await Promise.all([
      getFunnelSummary(dateRange),
      getRevenueSummary(),
      getConsentSummary(),
      getDeletionRequests(),
      getAiCallStats(),
      getRecentAiFailures(10),
      getGlobalSegments(),
      getPerAssessmentSegments(),
      getExperimentResults(),
    ]);

  const selectedAssessmentId = requestedAssessmentId ?? funnel[0]?.assessmentId;
  const dropoff = selectedAssessmentId ? await getQuestionDropoff(selectedAssessmentId) : null;
  const questionAnalytics = selectedAssessmentId ? await getRealQuestionAnalytics(selectedAssessmentId) : null;

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

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className={cardLabel}>Avg order value</p>
          <p className={cardValue}>{formatMoney(revenue.averageOrderValueCents)}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Revenue / visitor</p>
          <p className={cardValue}>{formatMoney(revenue.revenuePerVisitorCents)}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Revenue / assessment start</p>
          <p className={cardValue}>{formatMoney(revenue.revenuePerAssessmentStartCents)}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Revenue / completed assessment</p>
          <p className={cardValue}>{formatMoney(revenue.revenuePerCompletedAssessmentCents)}</p>
        </div>
      </div>

      <ReengagementRunner />
      <AbandonmentRunner />

      <div className="mb-6 flex items-center justify-between">
        <h2 className="font-display text-[18px] text-[var(--inner-ink)]">Funnel by experience</h2>
        <form method="GET" className="flex items-center gap-2 text-[12px] text-[var(--inner-ink-soft)]">
          <label htmlFor="analytics-from">From</label>
          <input
            id="analytics-from"
            type="date"
            name="from"
            defaultValue={from ?? ""}
            className="rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-2 py-1"
          />
          <label htmlFor="analytics-to">To</label>
          <input
            id="analytics-to"
            type="date"
            name="to"
            defaultValue={to ?? ""}
            className="rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-2 py-1"
          />
          <button type="submit" className="rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] px-3 py-1">
            Apply
          </button>
          {(from || to) && (
            <a href="/admin/analytics" className="text-[var(--inner-accent)] underline underline-offset-2">
              Clear
            </a>
          )}
        </form>
      </div>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Event counts only — no answer content is ever included here. Ranked by revenue. Funnel counts and revenue
        respect the date range above; the cards, drop-off, segments, and experiments below are all-time.
      </p>
      <div className="mb-8 overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Experience</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Revenue</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Conversion</th>
              {FUNNEL_STAGES.map((stage) => (
                <th key={stage.key} className="whitespace-nowrap px-4 py-3 font-medium">
                  {stage.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...funnel].sort((a, b) => b.revenueCents - a.revenueCents).map((row) => {
              const top = row.counts.landing_view ?? 0;
              return (
                <tr key={row.assessmentId} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">/{row.slug}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatMoney(row.revenueCents)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{row.conversionPct}%</td>
                  {FUNNEL_STAGES.map((stage, i) => {
                    const count = row.counts[stage.key] ?? 0;
                    const pctOfLanding = top > 0 ? Math.round((count / top) * 100) : null;
                    const prevCount = i > 0 ? (row.counts[FUNNEL_STAGES[i - 1].key] ?? 0) : null;
                    const pctOfPrev = prevCount && prevCount > 0 ? Math.round((count / prevCount) * 100) : null;
                    return (
                      <td key={stage.key} className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                        {count}
                        {pctOfPrev !== null && (
                          <span className="ml-1 text-[11px] text-[var(--inner-muted)]" title="of the previous step">
                            ({pctOfPrev}% step)
                          </span>
                        )}
                        {pctOfLanding !== null && stage.key !== "landing_view" && (
                          <span className="ml-1 text-[11px] text-[var(--inner-muted)]" title="of landing views">
                            ({pctOfLanding}% total)
                          </span>
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

      <h2 className="font-display mb-3 text-[18px] text-[var(--inner-ink)]">Question performance (real traffic)</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Views, answers, skip rate, and average response time from real sessions — distinct from the simulated
        100-persona QA run under LOVE QA. Never reads answer content.
      </p>
      <div className="mb-8 overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        {!questionAnalytics || questionAnalytics.questions.length === 0 ? (
          <p className="px-4 py-6 text-center text-[13px] text-[var(--inner-muted)]">
            No published core questions for this experience yet.
          </p>
        ) : (
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                <th className="px-4 py-3 font-medium">Question</th>
                <th className="whitespace-nowrap px-4 py-3 font-medium">Views</th>
                <th className="whitespace-nowrap px-4 py-3 font-medium">Answers</th>
                <th className="whitespace-nowrap px-4 py-3 font-medium">Skip rate</th>
                <th className="whitespace-nowrap px-4 py-3 font-medium">Avg. time</th>
              </tr>
            </thead>
            <tbody>
              {questionAnalytics.questions.map((q) => (
                <tr key={q.key} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="px-4 py-3 text-[var(--inner-ink)]">{q.prompt}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{q.views}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{q.answers}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                    {q.skipRatePct === null ? "—" : `${q.skipRatePct}%`}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                    {q.avgResponseTimeMs === null ? "—" : `${Math.round(q.avgResponseTimeMs / 1000)}s`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <h2 className="font-display mb-3 text-[18px] text-[var(--inner-ink)]">Segments</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Behavior-based only — never derived from assessment answers, profile results, or report content.
      </p>
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {globalSegments.map((s) => (
          <div key={s.key} className={card}>
            <p className={cardLabel}>{s.label}</p>
            <p className={cardValue}>{s.size}</p>
          </div>
        ))}
      </div>
      <div className="mb-8 overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="px-4 py-3 font-medium">Experience</th>
              <th className="px-4 py-3 font-medium">Completed segment</th>
              <th className="px-4 py-3 font-medium">Purchased segment</th>
            </tr>
          </thead>
          <tbody>
            {perAssessmentSegments.map((s) => (
              <tr key={s.slug} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="px-4 py-3 font-medium text-[var(--inner-ink)]">/{s.slug}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">
                  {s.slug.toUpperCase().replace(/-/g, "_")}_COMPLETED — {s.completed}
                </td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">
                  {s.slug.toUpperCase().replace(/-/g, "_")}_PURCHASED — {s.purchased}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="font-display mb-3 text-[18px] text-[var(--inner-ink)]">Experiments</h2>
      {experimentResults.length === 0 ? (
        <p className="mb-8 text-[13px] text-[var(--inner-ink-soft)]">
          No experiments running — the A/B foundation (lib/experiments.ts) is ready, nothing is configured yet.
        </p>
      ) : (
        <div className="mb-8 overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                <th className="px-4 py-3 font-medium">Experiment</th>
                <th className="px-4 py-3 font-medium">Variant</th>
                <th className="px-4 py-3 font-medium">Exposed</th>
                <th className="px-4 py-3 font-medium">Converted</th>
                <th className="px-4 py-3 font-medium">Conversion</th>
              </tr>
            </thead>
            <tbody>
              {experimentResults.map((r) => (
                <tr key={`${r.experimentId}-${r.variant}`} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="px-4 py-3 font-medium text-[var(--inner-ink)]">{r.experimentId}</td>
                  <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{r.variant}</td>
                  <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{r.exposed}</td>
                  <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{r.converted}</td>
                  <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{r.conversionPct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mb-8 flex items-center justify-between">
        <Link
          href="/admin/orders"
          className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-5 py-4 text-[15px] text-[var(--inner-ink)] hover:border-[var(--inner-accent-soft)]"
        >
          View all orders — payment status, provider, refunds →
        </Link>
        <a
          href="/api/admin/exports/orders"
          className="rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[13px] text-[var(--inner-ink-soft)] hover:border-[var(--inner-accent-soft)]"
        >
          Export CSV
        </a>
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
