import { getReportStatusCounts, listReportsForAdmin } from "@/lib/admin/reportsReader";
import { RetryReportButton } from "@/components/admin/RetryReportButton";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";

const STATUS_LABEL: Record<string, string> = {
  ready: "Ready",
  generating: "Generating",
  pending: "Pending",
  failed: "Failed",
};

export const dynamic = "force-dynamic";

export default async function AdminReportsPage() {
  const [counts, reports] = await Promise.all([getReportStatusCounts(), listReportsForAdmin(100)]);

  return (
    <div>
      <h1 className="font-display mb-6 text-[24px] text-[var(--inner-ink)]">Reports</h1>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div className={card}>
          <p className={cardLabel}>Ready</p>
          <p className={cardValue}>{counts.ready}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Generating</p>
          <p className={cardValue}>{counts.generating}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Pending</p>
          <p className={cardValue}>{counts.pending}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Generation failed</p>
          <p className={cardValue}>{counts.failed}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Email failed</p>
          <p className={cardValue}>{counts.emailFailed}</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Generated</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Experience</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Email</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Language</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Status</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">PDF</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Email status</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(r.generatedAt)}</td>
                <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">/{r.assessmentSlug}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{r.email}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{r.language}</td>
                <td className="px-4 py-3">
                  <span className={r.status === "failed" ? "text-[var(--inner-accent)]" : "text-[var(--inner-ink-soft)]"}>
                    {STATUS_LABEL[r.status] ?? r.status}
                  </span>
                  {r.failureReason && <p className="mt-1 max-w-[220px] text-[11px] text-[var(--inner-muted)]">{r.failureReason}</p>}
                </td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{r.hasPdf ? "Yes" : "—"}</td>
                <td className="px-4 py-3">
                  <span className={r.emailStatus === "failed" ? "text-[var(--inner-accent)]" : "text-[var(--inner-ink-soft)]"}>
                    {r.emailStatus === "n/a" ? "—" : r.emailStatus === "delivered" ? "Delivered" : "Failed"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-col gap-1">
                    {r.status === "failed" && <RetryReportButton reportId={r.id} kind="generation" />}
                    {r.status === "ready" && r.emailStatus === "failed" && <RetryReportButton reportId={r.id} kind="email" />}
                  </div>
                </td>
              </tr>
            ))}
            {reports.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No reports yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
