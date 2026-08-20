import { listPublishedSlugs, getAssessmentConfig } from "@/lib/assessments";
import { ReportPreviewPanel } from "@/components/admin/ReportPreviewPanel";

export const dynamic = "force-dynamic";

export default async function AdminReportPreviewPage() {
  const slugs = await listPublishedSlugs();
  const configs = await Promise.all(slugs.map((slug) => getAssessmentConfig(slug)));
  const assessments = configs
    .filter((c): c is NonNullable<typeof c> => c !== null)
    .map((c) => ({ slug: c.slug, name: c.name, profiles: c.profiles.map((p) => ({ key: p.key, name: p.name })) }));

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Report Preview</h1>
      <p className="mb-6 max-w-lg text-[13px] text-[var(--inner-ink-soft)]">
        Preview the live web report and PDF for any published assessment, built from synthesized sample evidence —
        never a real purchase or a real user's answers. Use this to check the effect of a report-structure or prompt
        change before it reaches a paying customer.
      </p>
      <ReportPreviewPanel assessments={assessments} />
    </div>
  );
}
