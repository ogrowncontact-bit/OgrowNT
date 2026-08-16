import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { nextQuestion } from "@inner/assessment-engine";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { reconstructSessionState } from "@/lib/sessionState";
import { toClientQuestion } from "@/lib/clientQuestion";
import { AssessmentFlow } from "@/components/AssessmentFlow";

export default async function SessionPage({ params }: { params: Promise<{ slug: string; id: string }> }) {
  const { slug, id } = await params;

  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) redirect(`/${slug}`);

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) notFound();
  if (session.status === "completed") redirect(`/${slug}/session/${id}/result`);

  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) notFound();

  const state = await reconstructSessionState(config, id);
  const question = nextQuestion(config, state);
  if (!question) redirect(`/${slug}/session/${id}/result`);

  return (
    <AssessmentFlow
      slug={slug}
      assessmentSessionId={id}
      initialQuestion={toClientQuestion(question)}
      initialProgress={{
        asked: state.askedQuestionKeys.length,
        recommended: config.recommendedQuestions,
        max: config.maxQuestions,
      }}
    />
  );
}
