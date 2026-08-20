import Link from "next/link";
import { prisma } from "@inner/db";
import { getAiCallStats, getRecentAiFailures } from "@/lib/admin/analyticsReader";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

export const dynamic = "force-dynamic";

export default async function AdminAiStudioPage() {
  const [stats, failures, qualityFailedCount, totalReports] = await Promise.all([
    getAiCallStats(),
    getRecentAiFailures(10),
    prisma.event.count({ where: { eventName: "report_quality_check_failed" } }),
    prisma.report.count({ where: { status: "ready" } }),
  ]);

  const totalCalls = stats.reduce((sum, s) => sum + s.totalCalls, 0);
  const totalOk = stats.reduce((sum, s) => sum + s.okCalls, 0);
  const qualityPassRatePct = totalReports > 0 ? Math.round(((totalReports - qualityFailedCount) / totalReports) * 1000) / 10 : null;

  return (
    <div>
      <h1 className="font-display mb-6 text-[24px] text-[var(--inner-ink)]">AI Studio</h1>

      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <Link href="/admin/ai-settings" className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5 hover:border-[var(--inner-accent-soft)]">
          <h2 className="font-display text-[16px] text-[var(--inner-ink)]">Model Configuration</h2>
          <p className="mt-2 text-[13px] text-[var(--inner-ink-soft)]">Provider and model routing for quick analysis, premium reports, and fallback.</p>
        </Link>
        <Link href="/admin/ai/prompts" className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5 hover:border-[var(--inner-accent-soft)]">
          <h2 className="font-display text-[16px] text-[var(--inner-ink)]">Prompts</h2>
          <p className="mt-2 text-[13px] text-[var(--inner-ink-soft)]">Global persona, per-assessment personas, prompt versions, and the playground.</p>
        </Link>
        <Link href="/admin/reports/preview" className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5 hover:border-[var(--inner-accent-soft)]">
          <h2 className="font-display text-[16px] text-[var(--inner-ink)]">Report Preview</h2>
          <p className="mt-2 text-[13px] text-[var(--inner-ink-soft)]">Generate a sample report with real synthetic evidence — web and PDF.</p>
        </Link>
      </div>

      <h2 className="font-display mb-3 text-[16px] text-[var(--inner-ink)]">Generation logs</h2>
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4">
          <p className="text-[12px] text-[var(--inner-muted)]">Generations</p>
          <p className="font-display text-[20px] text-[var(--inner-ink)]">{totalCalls}</p>
        </div>
        <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4">
          <p className="text-[12px] text-[var(--inner-muted)]">Success rate</p>
          <p className="font-display text-[20px] text-[var(--inner-ink)]">{totalCalls > 0 ? Math.round((totalOk / totalCalls) * 1000) / 10 : 0}%</p>
        </div>
        <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4">
          <p className="text-[12px] text-[var(--inner-muted)]">Failures</p>
          <p className="font-display text-[20px] text-[var(--inner-ink)]">{totalCalls - totalOk}</p>
        </div>
        <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4">
          <p className="text-[12px] text-[var(--inner-muted)]">Quality gate pass rate</p>
          <p className="font-display text-[20px] text-[var(--inner-ink)]">{qualityPassRatePct === null ? "—" : `${qualityPassRatePct}%`}</p>
        </div>
      </div>
      <p className="mb-6 text-[12px] text-[var(--inner-ink-soft)]">
        &quot;Fallback&quot; and &quot;manual review&quot; counts aren&apos;t separately instrumented yet — every module already
        degrades to a deterministic template on failure (see reportAI.ts/questionAI.ts), but which of the successes above were
        AI-generated vs. fallback isn&apos;t logged as its own signal today.
      </p>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Module</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Calls</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Success</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Avg latency</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Avg tokens (in/out)</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((s) => (
              <tr key={s.module} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">{s.module}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{s.totalCalls}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{s.okCalls}/{s.totalCalls}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{s.avgLatencyMs}ms</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                  {s.totalCalls > 0 ? Math.round(s.totalInputTokens / s.totalCalls) : 0} / {s.totalCalls > 0 ? Math.round(s.totalOutputTokens / s.totalCalls) : 0}
                </td>
              </tr>
            ))}
            {stats.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No AI calls logged yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {failures.length > 0 && (
        <>
          <h2 className="font-display mb-3 mt-8 text-[16px] text-[var(--inner-ink)]">Recent failures</h2>
          <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                  <th className="whitespace-nowrap px-4 py-3 font-medium">When</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">Module</th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {failures.map((f) => (
                  <tr key={f.id} className="border-b border-[var(--inner-line)] last:border-0">
                    <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(f.occurredAt)}</td>
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">{f.module}</td>
                    <td className="px-4 py-3 text-[var(--inner-muted)]">{f.errorReason ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
