import Link from "next/link";
import { redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen } from "@inner/ui";
import { readAccessUserId } from "@/lib/access";
import { getAssessmentConfig } from "@/lib/assessments";

export const dynamic = "force-dynamic";
export const metadata = { robots: { index: false, follow: false } };

export default async function AccessReportsPage() {
  const userId = await readAccessUserId();
  if (!userId) redirect("/access");

  const reports = await prisma.report.findMany({
    where: { order: { userId } },
    orderBy: { generatedAt: "desc" },
    include: { order: { include: { price: { include: { assessment: true } } } }, assessmentSession: true },
  });

  const profileResults = await prisma.profileResult.findMany({
    where: { assessmentSessionId: { in: reports.map((r) => r.assessmentSessionId) } },
  });
  const configsBySlug = new Map(
    await Promise.all(
      [...new Set(reports.map((r) => r.assessmentSession.sourceSlug))].map(
        async (slug) => [slug, await getAssessmentConfig(slug)] as const
      )
    )
  );

  return (
    <Screen align="top">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Your reports</p>
      <h1 className="font-display text-[26px] leading-tight text-[var(--inner-ink)]">Everything you&apos;ve unlocked</h1>

      {reports.length === 0 ? (
        <p className="mt-6 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
          We didn&apos;t find any purchased reports on this account yet.
        </p>
      ) : (
        <div className="mt-8 space-y-4 pb-12">
          {reports.map((report) => {
            const config = configsBySlug.get(report.assessmentSession.sourceSlug);
            const profileResult = profileResults.find((p) => p.assessmentSessionId === report.assessmentSessionId);
            const profileName =
              config?.profiles.find((p) => p.key === profileResult?.primaryProfileKey)?.name ??
              report.order.price.assessment.name;

            return (
              <Link
                key={report.id}
                href={`/${report.assessmentSession.sourceSlug}/session/${report.assessmentSessionId}/report`}
                className="block rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
                    {report.order.price.assessment.name}
                  </p>
                  {report.status !== "ready" && (
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        report.status === "failed"
                          ? "bg-[var(--inner-accent)] text-[var(--inner-accent-contrast)]"
                          : "bg-[var(--inner-paper-dim)] text-[var(--inner-muted)]"
                      }`}
                    >
                      {report.status === "generating" || report.status === "pending" ? "Preparing" : "Failed"}
                    </span>
                  )}
                </div>
                <h2 className="mt-1 font-display text-[19px] text-[var(--inner-ink)]">{profileName}</h2>
                <p className="mt-2 text-[13px] text-[var(--inner-muted)]">
                  {new Date(report.generatedAt).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </p>
              </Link>
            );
          })}
        </div>
      )}

      <p className="mb-8 text-[13px] text-[var(--inner-muted)]">
        <Link href="/preferences" className="underline">
          Email preferences
        </Link>
      </p>
    </Screen>
  );
}
