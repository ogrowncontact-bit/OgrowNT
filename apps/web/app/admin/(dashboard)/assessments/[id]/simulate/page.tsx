import { notFound } from "next/navigation";
import { prisma } from "@inner/db";
import Link from "next/link";
import { AssessmentSimulator } from "@/components/admin/AssessmentSimulator";

export default async function AssessmentSimulatePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const assessment = await prisma.assessment.findUnique({ where: { id } });
  if (!assessment) notFound();

  return (
    <div>
      <div className="mb-6">
        <Link href={`/admin/assessments/${id}`} className="text-[13px] text-[var(--inner-accent)] underline underline-offset-2">
          ← Back to editor
        </Link>
        <h1 className="font-display mt-2 text-[24px] text-[var(--inner-ink)]">Simulate: {assessment.name}</h1>
        <p className="mt-1 text-[13px] text-[var(--inner-ink-soft)]">
          Runs the real deterministic adaptive engine against this assessment's current draft (or latest published
          version). Nothing here is persisted — no real session, no analytics events.
        </p>
      </div>
      <AssessmentSimulator assessmentId={id} />
    </div>
  );
}
