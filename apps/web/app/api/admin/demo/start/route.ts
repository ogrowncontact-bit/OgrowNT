import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { startSession, nextQuestion } from "@inner/assessment-engine";
import { requireAdminWriter } from "@/lib/adminAuth";
import { getAssessmentConfig } from "@/lib/assessments";
import { getAiModelConfig } from "@/lib/aiConfig";
import { ensureAnonymousSession } from "@/lib/anonymousSession";
import { recordSessionAnswer } from "@/lib/recordSessionAnswer";
import { completeAssessmentSession } from "@/lib/completeAssessmentSession";
import { chooseAnswerForPersona } from "@/lib/demoAnswerSelection";
import { getDemoPersona } from "@/lib/demoPersonas";
import { checkRateLimit } from "@/lib/security/rateLimit";
import { logAdminAction } from "@/lib/auditLog";
import { track } from "@/lib/analytics";
import { ensureAiTelemetryRegistered } from "@/lib/aiTelemetry";

ensureAiTelemetryRegistered();

// FASE 29 §DEMO PERSONAS/§DEMO CONTROL — admin-gated only, never reachable by
// a production visitor. Walks the *real* engine (startSession/nextQuestion/
// submitAnswer, via the same recordSessionAnswer/completeAssessmentSession
// the live answer route uses) with programmatically-selected real answers,
// landing the admin on the actual public result page. Scoped to LOVE only,
// matching the mega-spec's 5 named LOVE personas.
const DEMO_SLUG = "love";
const MAX_STEPS_GUARD = 60; // LOVE's own maxQuestions tops out at 18 — this only guards against a genuine adaptive-rule infinite loop.

export async function POST(request: NextRequest) {
  const admin = await requireAdminWriter();

  const { allowed } = await checkRateLimit("admin_demo_start", admin.id, { maxAttempts: 20, windowMs: 60 * 60 * 1000 });
  if (!allowed) {
    return NextResponse.json({ error: "Too many demo sessions started recently — try again in a few minutes." }, { status: 429 });
  }

  const body = await request.json().catch(() => null);
  const personaKey = body?.personaKey as string | undefined;
  const persona = personaKey ? getDemoPersona(personaKey) : undefined;
  if (!persona) return NextResponse.json({ error: "Unknown demo persona" }, { status: 400 });

  const config = await getAssessmentConfig(DEMO_SLUG);
  if (!config) return NextResponse.json({ error: "LOVE assessment is not available" }, { status: 500 });

  const assessment = await prisma.assessment.findUnique({ where: { slug: DEMO_SLUG } });
  if (!assessment) return NextResponse.json({ error: "LOVE assessment is not seeded" }, { status: 500 });

  const version = await prisma.assessmentVersion.findFirst({
    where: { assessmentId: assessment.id, publishedAt: { not: null } },
    orderBy: { versionNumber: "desc" },
  });
  if (!version) return NextResponse.json({ error: "LOVE assessment has no published version" }, { status: 500 });

  const modelConfig = await getAiModelConfig();
  const anonymousSessionId = await ensureAnonymousSession({ firstLandingSlug: DEMO_SLUG });

  const session = await prisma.assessmentSession.create({
    data: { anonymousSessionId, assessmentId: assessment.id, assessmentVersionId: version.id, sourceSlug: DEMO_SLUG },
  });

  await track({
    anonymousSessionId,
    eventName: "assessment_started",
    assessmentId: assessment.id,
    properties: { demoPersonaKey: persona.key },
  });

  let state = startSession(config);
  for (let step = 0; step < MAX_STEPS_GUARD; step++) {
    const question = nextQuestion(config, state);
    if (!question) break;

    const answer = chooseAnswerForPersona(question, persona, state);
    const { result } = await recordSessionAnswer({
      id: session.id,
      anonymousSessionId,
      assessmentId: assessment.id,
      config,
      state,
      expected: question,
      questionKey: question.key,
      selectedOptionKeys: answer.selectedOptionKeys,
      scaleValue: answer.scaleValue,
      openText: answer.openText,
      skipped: false,
      modelConfig,
    });
    state = result.state;

    if (result.isComplete) {
      await completeAssessmentSession({
        id: session.id,
        anonymousSessionId,
        assessmentId: assessment.id,
        config,
        state,
        modelConfig,
      });
      break;
    }
  }

  await logAdminAction({
    adminUserId: admin.id,
    action: "Start Demo Session",
    entityType: "AssessmentSession",
    entityId: session.id,
    diff: { personaKey: persona.key, slug: DEMO_SLUG },
  });

  return NextResponse.json({ resultUrl: `/${DEMO_SLUG}/session/${session.id}/result` });
}
