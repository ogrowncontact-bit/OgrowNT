import Link from "next/link";
import { getDashboardOverview, getTopAcquisitionSources, getTopAssessments, getTopCampaigns, getTopRecommendations } from "@/lib/admin/dashboardReader";
import { getReportStatusCounts } from "@/lib/admin/reportsReader";
import { formatPrice as formatMoney } from "@/lib/money";

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";
const sectionCard = "overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]";

export const dynamic = "force-dynamic";

export default async function AdminHomePage() {
  const [overview, reportCounts, topAssessments, topSources, topCampaigns, topRecommendations] = await Promise.all([
    getDashboardOverview(),
    getReportStatusCounts(),
    getTopAssessments(5),
    getTopAcquisitionSources(5),
    getTopCampaigns(5),
    getTopRecommendations(5),
  ]);

  return (
    <div>
      <h1 className="font-display mb-6 text-[24px] text-[var(--inner-ink)]">INNER Control Center</h1>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className={cardLabel}>Today&apos;s visitors</p>
          <p className={cardValue}>{overview.todaysVisitors}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Assessment starts</p>
          <p className={cardValue}>{overview.totalStartedSessions}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Completed assessments</p>
          <p className={cardValue}>{overview.totalCompletedSessions}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Purchases</p>
          <p className={cardValue}>{overview.totalPaidOrders}</p>
        </div>
      </div>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className={cardLabel}>Revenue (paid)</p>
          <p className={cardValue}>{formatMoney(overview.totalRevenueCents)}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Conversion (completed → paid)</p>
          <p className={cardValue}>{overview.completionToPaidConversionPct}%</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Experiences live</p>
          <p className={cardValue}>{overview.publishedAssessments}</p>
          <p className={cardLabel}>{overview.totalAssessments} total</p>
        </div>
        <Link href="/admin/orders" className={`${card} hover:border-[var(--inner-accent-soft)]`}>
          <p className={cardLabel}>Payments pending</p>
          <p className={`${cardValue} ${overview.pendingOrders > 0 ? "text-[var(--inner-accent)]" : ""}`}>{overview.pendingOrders}</p>
        </Link>
      </div>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Link href="/admin/reports" className={`${card} hover:border-[var(--inner-accent-soft)]`}>
          <p className={cardLabel}>Reports pending</p>
          <p className={cardValue}>{reportCounts.pending + reportCounts.generating}</p>
        </Link>
        <div className={card}>
          <p className={cardLabel}>Reports ready</p>
          <p className={cardValue}>{reportCounts.ready}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Reports failed</p>
          <p className={`${cardValue} ${reportCounts.failed > 0 ? "text-[var(--inner-accent)]" : ""}`}>{reportCounts.failed}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Emails failed</p>
          <p className={`${cardValue} ${reportCounts.emailFailed > 0 ? "text-[var(--inner-accent)]" : ""}`}>{reportCounts.emailFailed}</p>
        </div>
        <Link href="/admin/reports" className={`${card} flex items-center justify-center hover:border-[var(--inner-accent-soft)]`}>
          <p className="text-[13px] text-[var(--inner-ink-soft)]">View all reports →</p>
        </Link>
      </div>

      <div className="mb-8 grid gap-6 sm:grid-cols-2">
        <div>
          <h2 className="font-display mb-3 text-[16px] text-[var(--inner-ink)]">Top experiences</h2>
          <div className={sectionCard}>
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                  <th className="px-4 py-3 font-medium">Experience</th>
                  <th className="px-4 py-3 font-medium">Completions</th>
                  <th className="px-4 py-3 font-medium">Paid</th>
                </tr>
              </thead>
              <tbody>
                {topAssessments.map((a) => (
                  <tr key={a.slug} className="border-b border-[var(--inner-line)] last:border-0">
                    <td className="px-4 py-3 font-medium text-[var(--inner-ink)]">/{a.slug}</td>
                    <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{a.completions}</td>
                    <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{a.paidOrders}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h2 className="font-display mb-3 text-[16px] text-[var(--inner-ink)]">Top acquisition sources</h2>
          <div className={sectionCard}>
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                  <th className="px-4 py-3 font-medium">Source</th>
                  <th className="px-4 py-3 font-medium">Sessions</th>
                  <th className="px-4 py-3 font-medium">Paid</th>
                </tr>
              </thead>
              <tbody>
                {topSources.map((s) => (
                  <tr key={s.source} className="border-b border-[var(--inner-line)] last:border-0">
                    <td className="px-4 py-3 font-medium text-[var(--inner-ink)]">{s.source}</td>
                    <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{s.sessions}</td>
                    <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{s.paidOrders}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {topCampaigns.length > 0 && (
        <div className="mb-8">
          <h2 className="font-display mb-3 text-[16px] text-[var(--inner-ink)]">Top campaigns</h2>
          <div className={sectionCard}>
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                  <th className="px-4 py-3 font-medium">Source</th>
                  <th className="px-4 py-3 font-medium">Campaign</th>
                  <th className="px-4 py-3 font-medium">Sessions</th>
                  <th className="px-4 py-3 font-medium">Paid</th>
                </tr>
              </thead>
              <tbody>
                {topCampaigns.map((c) => (
                  <tr key={`${c.source}-${c.campaign}`} className="border-b border-[var(--inner-line)] last:border-0">
                    <td className="px-4 py-3 font-medium text-[var(--inner-ink)]">{c.source}</td>
                    <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{c.campaign}</td>
                    <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{c.sessions}</td>
                    <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{c.paidOrders}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <h2 className="font-display mb-3 text-[16px] text-[var(--inner-ink)]">Top recommendation edges</h2>
      <p className="mb-3 text-[13px] text-[var(--inner-ink-soft)]">
        Ranked by report-page impressions — no per-click tracking exists yet, so this reflects exposure, not conversion.
      </p>
      <div className={`${sectionCard} mb-8`}>
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="px-4 py-3 font-medium">From</th>
              <th className="px-4 py-3 font-medium">To</th>
              <th className="px-4 py-3 font-medium">Weight</th>
              <th className="px-4 py-3 font-medium">Impressions</th>
            </tr>
          </thead>
          <tbody>
            {topRecommendations.map((r, i) => (
              <tr key={`${r.fromSlug}-${r.toSlug}-${i}`} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="px-4 py-3 font-medium text-[var(--inner-ink)]">/{r.fromSlug}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">/{r.toSlug}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{r.weight}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{r.impressions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          href="/admin/assessments"
          className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5 hover:border-[var(--inner-accent-soft)]"
        >
          <h2 className="font-display text-[17px] text-[var(--inner-ink)]">Assessments</h2>
          <p className="mt-2 text-[14px] text-[var(--inner-ink-soft)]">
            Create, edit, and publish INNER experiences without a deploy.
          </p>
        </Link>
        <Link
          href="/admin/analytics"
          className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5 hover:border-[var(--inner-accent-soft)]"
        >
          <h2 className="font-display text-[17px] text-[var(--inner-ink)]">Analytics</h2>
          <p className="mt-2 text-[14px] text-[var(--inner-ink-soft)]">
            Funnel conversion, purchases, and marketing consent — per assessment.
          </p>
        </Link>
      </div>
    </div>
  );
}
