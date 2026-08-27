import { prisma } from "@inner/db";
import {
  getLoveAssessment,
  getLoveTrafficStats,
  getLoveReportPipelineStats,
  getLoveDailySummary,
  getLoveAbandonmentReasons,
  getLovePurchaseReasons,
} from "@/lib/admin/launchReader";
import { FUNNEL_STAGES, getFunnelSummary, getAiCallStats, getRecentAiFailures } from "@/lib/admin/analyticsReader";
import { getRealQuestionAnalytics } from "@/lib/admin/questionAnalyticsReader";
import { getFeedbackSummary, listFeedback, RATING_LABELS } from "@/lib/admin/feedbackReader";
import { getEmergencyControls } from "@/lib/emergencyControls";
import { getLaunchModeSlug, getSoftLaunchMaxUsers, isSoftLaunchDiagnosticsEnabled } from "@/lib/launchMode";
import { formatPrice } from "@/lib/money";
import { EmergencyControlsPanel } from "@/components/admin/EmergencyControlsPanel";

export const dynamic = "force-dynamic";

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";
const sectionTitle = "font-display mb-3 mt-10 text-[18px] text-[var(--inner-ink)]";

const ABANDONMENT_LABEL: Record<string, string> = {
  too_expensive: "Too expensive",
  not_sure_useful: "Not sure it would be useful",
  wanted_to_think: "Wanted to think about it",
  not_enough_info: "Not enough information",
  technical_problem: "Technical problem",
  other: "Other",
};

const PURCHASE_LABEL: Record<string, string> = {
  curiosity: "Curiosity",
  free_result_accurate: "The free result felt accurate",
  wanted_more_detail: "I wanted more detail",
  preview_convinced: "The preview convinced me",
  price_reasonable: "Price felt reasonable",
  other: "Other",
};

const CHECKLIST_ITEMS = [
  "Domain",
  "SSL",
  "Payment",
  "Webhooks",
  "Email",
  "PDF",
  "AI",
  "Analytics",
  "Privacy",
  "Terms",
  "Refund",
  "Mobile",
  "Error monitoring",
  "Backup",
];

/**
 * FASE 33 §SOFT LAUNCH DASHBOARD — "mission control" for the LOVE soft
 * launch: traffic/funnel/questions/sales/reports/feedback/AI/technical
 * health, a daily summary, emergency controls, and a manual launch
 * checklist. Composes existing readers rather than re-deriving their logic;
 * see lib/admin/launchReader.ts for what's genuinely LOVE-scoped vs
 * platform-wide (AI call stats have no per-assessment scoping in this
 * schema, so that section is honestly labelled platform-wide).
 */
export default async function LoveLaunchDashboard() {
  const assessment = await getLoveAssessment();
  if (!assessment) {
    return (
      <div>
        <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">LOVE Launch</h1>
        <p className="text-[13px] text-[var(--inner-ink-soft)]">No assessment with slug &quot;love&quot; exists yet.</p>
      </div>
    );
  }

  const [
    daily,
    traffic,
    funnel,
    questionAnalytics,
    reportPipeline,
    feedbackSummary,
    recentFeedback,
    abandonmentReasons,
    purchaseReasons,
    aiStats,
    aiFailures,
    emergencyControls,
    refundCount,
    openSupportCount,
  ] = await Promise.all([
    getLoveDailySummary(assessment.id),
    getLoveTrafficStats(assessment.id),
    getFunnelSummary(),
    getRealQuestionAnalytics(assessment.id),
    getLoveReportPipelineStats(assessment.id),
    getFeedbackSummary(),
    listFeedback({ assessmentSlug: "love" }, 10),
    getLoveAbandonmentReasons(assessment.id),
    getLovePurchaseReasons(assessment.id),
    getAiCallStats(),
    getRecentAiFailures(10),
    getEmergencyControls(),
    prisma.refund.count({ where: { order: { assessmentSession: { assessmentId: assessment.id } } } }),
    prisma.supportTicket.count({ where: { status: "open" } }),
  ]);

  const loveFunnelRow = funnel.find((f) => f.assessmentId === assessment.id);
  const launchModeSlug = getLaunchModeSlug();
  const softLaunchMax = getSoftLaunchMaxUsers();
  const softLaunchDiagnostics = isSoftLaunchDiagnosticsEnabled();

  return (
    <div>
      <h1 className="font-display mb-1 text-[24px] text-[var(--inner-ink)]">LOVE Launch</h1>
      <p className="mb-6 text-[13px] text-[var(--inner-ink-soft)]">
        LOVE {assessment.releaseVersion} · {launchModeSlug === "love" ? "Soft launch: catalog restricted to LOVE" : "Full catalog live"}
        {softLaunchMax !== null && ` · Cap ${softLaunchMax} visitors`}
        {softLaunchDiagnostics && " · Diagnostics ON"}
      </p>

      <div className="mb-8 grid gap-4 md:grid-cols-2">
        <div className={card}>
          <p className="mb-3 text-[13px] font-medium text-[var(--inner-ink)]">Today</p>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <p className={cardLabel}>Visitors</p>
              <p className={cardValue}>{daily.visitors}</p>
            </div>
            <div>
              <p className={cardLabel}>Starts</p>
              <p className={cardValue}>{daily.starts}</p>
            </div>
            <div>
              <p className={cardLabel}>Completions</p>
              <p className={cardValue}>{daily.completions}</p>
            </div>
            <div>
              <p className={cardLabel}>Purchases</p>
              <p className={cardValue}>{daily.purchases}</p>
            </div>
            <div>
              <p className={cardLabel}>Revenue</p>
              <p className={cardValue}>{formatPrice(daily.revenueCents)}</p>
            </div>
            <div>
              <p className={cardLabel}>Conversion</p>
              <p className={cardValue}>{daily.conversionPct}%</p>
            </div>
          </div>
          <div className="mt-4 space-y-1 border-t border-[var(--inner-line)] pt-3 text-[12px] text-[var(--inner-ink-soft)]">
            <p>
              Avg. report rating: {daily.avgRating !== null ? `${daily.avgRating} / 5` : "No ratings yet today"}
              {daily.mostCommonRating && ` (most common: ${RATING_LABELS[daily.mostCommonRating as keyof typeof RATING_LABELS] ?? daily.mostCommonRating})`}
            </p>
            <p>
              Top abandonment reason today:{" "}
              {daily.topAbandonmentReason ? ABANDONMENT_LABEL[daily.topAbandonmentReason] ?? daily.topAbandonmentReason : "None reported"}
            </p>
            <p>Technical errors today: {daily.technicalErrors} <span className="text-[var(--inner-muted)]">(report + AI + email failures; AI is platform-wide)</span></p>
          </div>
        </div>

        <EmergencyControlsPanel
          initialPurchasesPaused={emergencyControls.purchasesPaused}
          initialReportGenerationPaused={emergencyControls.reportGenerationPaused}
          initialAiForceFallback={emergencyControls.aiForceFallback}
        />
      </div>

      <h2 className={sectionTitle}>Traffic</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className={cardLabel}>Real visitors (all-time)</p>
          <p className={cardValue}>{traffic.totalVisitors}</p>
        </div>
        {traffic.deviceBreakdown.map((d) => (
          <div key={d.device} className={card}>
            <p className={cardLabel}>{d.device}</p>
            <p className={cardValue}>{d.count}</p>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-[var(--inner-muted)]">
        Excludes FASE 31&apos;s simulated QA-persona sessions. Device is a coarse classification from the user-agent —
        &quot;unknown&quot; includes visitors from before this field existed.
      </p>

      <h2 className={sectionTitle}>Funnel</h2>
      {loveFunnelRow ? (
        <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                {FUNNEL_STAGES.map((s) => (
                  <th key={s.key} className="whitespace-nowrap px-4 py-3 font-medium">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {FUNNEL_STAGES.map((s) => (
                  <td key={s.key} className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                    {loveFunnelRow.counts[s.key] ?? 0}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-[13px] text-[var(--inner-muted)]">No funnel data yet.</p>
      )}

      <h2 className={sectionTitle}>Questions</h2>
      {questionAnalytics && questionAnalytics.questions.length > 0 ? (
        <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
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
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{q.skipRatePct === null ? "—" : `${q.skipRatePct}%`}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                    {q.avgResponseTimeMs === null ? "—" : `${Math.round(q.avgResponseTimeMs / 1000)}s`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-[13px] text-[var(--inner-muted)]">No question data yet.</p>
      )}

      <h2 className={sectionTitle}>Sales</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className={cardLabel}>Revenue (all-time)</p>
          <p className={cardValue}>{formatPrice(loveFunnelRow?.revenueCents ?? 0)}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Purchases</p>
          <p className={cardValue}>{loveFunnelRow?.counts.payment_completed ?? 0}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Refunds</p>
          <p className={cardValue}>{refundCount}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Visitor → Purchase</p>
          <p className={cardValue}>{loveFunnelRow?.conversionPct ?? 0}%</p>
        </div>
      </div>

      <h2 className={sectionTitle}>Reports</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div className={card}>
          <p className={cardLabel}>Generation started</p>
          <p className={cardValue}>{reportPipeline.started}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Ready</p>
          <p className={cardValue}>{reportPipeline.ready}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Failed</p>
          <p className={cardValue}>{reportPipeline.failed}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Emailed</p>
          <p className={cardValue}>{reportPipeline.delivered}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Email failed</p>
          <p className={cardValue}>{reportPipeline.emailFailed}</p>
        </div>
      </div>

      <h2 className={sectionTitle}>Feedback</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <div className={card}>
          <p className="mb-2 text-[13px] font-medium text-[var(--inner-ink)]">Report accuracy ({feedbackSummary.total} total, all products)</p>
          {feedbackSummary.byRating.length === 0 ? (
            <p className="text-[13px] text-[var(--inner-muted)]">No feedback yet.</p>
          ) : (
            <ul className="space-y-1 text-[13px] text-[var(--inner-ink-soft)]">
              {feedbackSummary.byRating.map((r) => (
                <li key={r.rating}>
                  {RATING_LABELS[r.rating]}: {r.count}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className={card}>
          <p className="mb-2 text-[13px] font-medium text-[var(--inner-ink)]">Why they purchased</p>
          {purchaseReasons.length === 0 ? (
            <p className="text-[13px] text-[var(--inner-muted)]">No purchase feedback yet.</p>
          ) : (
            <ul className="space-y-1 text-[13px] text-[var(--inner-ink-soft)]">
              {purchaseReasons.map((r) => (
                <li key={r.reason}>
                  {PURCHASE_LABEL[r.reason] ?? r.reason}: {r.count}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className={card}>
          <p className="mb-2 text-[13px] font-medium text-[var(--inner-ink)]">Why they didn&apos;t (abandonment)</p>
          {abandonmentReasons.length === 0 ? (
            <p className="text-[13px] text-[var(--inner-muted)]">No abandonment feedback yet.</p>
          ) : (
            <ul className="space-y-1 text-[13px] text-[var(--inner-ink-soft)]">
              {abandonmentReasons.map((r) => (
                <li key={r.reason}>
                  {ABANDONMENT_LABEL[r.reason] ?? r.reason}: {r.count}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <p className="mt-3 text-[13px] text-[var(--inner-ink-soft)]">
        Open support tickets: {openSupportCount} — see <a href="/admin/support" className="underline">Support</a>.
      </p>
      {recentFeedback.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                <th className="px-4 py-3 font-medium">Rating</th>
                <th className="px-4 py-3 font-medium">Comment</th>
              </tr>
            </thead>
            <tbody>
              {recentFeedback.map((f) => (
                <tr key={f.id} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{RATING_LABELS[f.rating]}</td>
                  <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{f.comment ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className={sectionTitle}>AI</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Platform-wide — AiCallLog has no per-assessment scoping in this schema, so this covers every AI-touching
        product, not LOVE alone. Meaningful while LOVE is the only one taking real traffic.
      </p>
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {aiStats.length === 0 ? (
          <p className="text-[13px] text-[var(--inner-muted)]">No AI calls logged.</p>
        ) : (
          aiStats.map((s) => (
            <div key={s.module} className={card}>
              <p className={cardLabel}>{s.module}</p>
              <p className={cardValue}>
                {s.okCalls}/{s.totalCalls}
              </p>
              <p className={cardLabel}>{s.avgLatencyMs}ms avg</p>
            </div>
          ))
        )}
      </div>
      {aiFailures.length > 0 && (
        <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                <th className="px-4 py-3 font-medium">When</th>
                <th className="px-4 py-3 font-medium">Module</th>
                <th className="px-4 py-3 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {aiFailures.map((f) => (
                <tr key={f.id} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                    {new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(f.occurredAt)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink)]">{f.module}</td>
                  <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{f.errorReason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className={sectionTitle}>Technical health</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        No dedicated error-log system exists yet — this rolls up the failure signals that already do: failed report
        generation, failed AI calls, and failed report emails.
      </p>
      <div className="grid grid-cols-3 gap-3">
        <div className={card}>
          <p className={cardLabel}>Report generation failures</p>
          <p className={cardValue}>{reportPipeline.failed}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>AI call failures (platform-wide)</p>
          <p className={cardValue}>{aiStats.reduce((sum, s) => sum + (s.totalCalls - s.okCalls), 0)}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Report email failures</p>
          <p className={cardValue}>{reportPipeline.emailFailed}</p>
        </div>
      </div>

      <h2 className={sectionTitle}>Launch checklist</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Manual reference — production infrastructure (domain/SSL/DNS records, real provider credentials) can&apos;t be
        verified from inside this environment. See the FASE 33 deliverable for what&apos;s genuinely confirmed vs. what
        needs a person to check. Cross-reference{" "}
        <a href="/admin/settings" className="underline">
          Settings
        </a>{" "}
        for live provider-configuration status.
      </p>
      <ul className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        {CHECKLIST_ITEMS.map((item) => (
          <li key={item} className="flex items-center gap-2 text-[13px] text-[var(--inner-ink-soft)]">
            <span className="inline-block h-4 w-4 shrink-0 rounded-sm border border-[var(--inner-line)]" aria-hidden="true" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
