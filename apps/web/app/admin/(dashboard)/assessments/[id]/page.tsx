import { notFound } from "next/navigation";
import { prisma } from "@inner/db";
import { dimensionPool } from "@inner/content/dimensions";
import { loadAssessmentForEdit, listAssessmentsForAdmin, listVersionHistory } from "@/lib/admin/catalogReader";
import { getLandingContentOverrides } from "@/lib/landingContent";
import { AssessmentEditor } from "@/components/admin/AssessmentEditor";

export default async function AssessmentBuilderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const assessment = await prisma.assessment.findUnique({ where: { id } });
  if (!assessment) notFound();

  const loaded = await loadAssessmentForEdit(id);
  if (!loaded) notFound();

  const [otherAssessments, initialLandingContent, versionHistory] = await Promise.all([
    listAssessmentsForAdmin(),
    getLandingContentOverrides(assessment.slug),
    listVersionHistory(id),
  ]);

  return (
    <AssessmentEditor
      assessmentId={id}
      initialConfig={loaded.config}
      hasDraft={loaded.hasDraft}
      status={assessment.status}
      dimensionPool={dimensionPool}
      otherAssessmentSlugs={otherAssessments.filter((a) => a.id !== id).map((a) => a.slug)}
      initialLandingContent={initialLandingContent}
      versionHistory={versionHistory}
    />
  );
}
