import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { nextQuestion } from "@inner/assessment-engine";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { reconstructSessionState } from "@/lib/sessionState";
import { toClientQuestion } from "@/lib/clientQuestion";
import { ensureAiTelemetryRegistered } from "@/lib/aiTelemetry";
import { getAiModelConfig } from "@/lib/aiConfig";
import { completeAssessmentSession } from "@/lib/completeAssessmentSession";
import { recordSessionAnswer } from "@/lib/recordSessionAnswer";

// Registers once per module instance — instrumentation.ts's startup hook runs
// in a separate module realm from route handlers in Next.js's dev server, so
// it alone isn't a reliable place to register a handler this file's own
// callStructured() calls need to see. Idempotent, cheap to call again here.
ensureAiTelemetryRegistered();

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) return NextResponse.json({ error: "No session" }, { status: 401 });

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  if (session.status === "completed") {
    return NextResponse.json({ error: "Assessment already completed" }, { status: 409 });
  }

  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) return NextResponse.json({ error: "Unknown assessment" }, { status: 500 });

  const modelConfig = await getAiModelConfig();

  const body = await request.json().catch(() => null);
  const questionKey = body?.questionKey as string | undefined;
  if (!questionKey) return NextResponse.json({ error: "questionKey is required" }, { status: 400 });

  const state = await reconstructSessionState(config, id);
  const expected = nextQuestion(config, state);
  if (!expected || expected.key !== questionKey) {
    return NextResponse.json({ error: "This is not the current question for this session" }, { status: 400 });
  }

  const selectedOptionKeys = body?.selectedOptionKeys as string[] | undefined;
  const scaleValue = body?.scaleValue as number | undefined;
  const openText = body?.openText as string | undefined;
  const skipped = body?.skipped === true;
  if (skipped && !expected.sensitive) {
    return NextResponse.json({ error: "This question cannot be skipped" }, { status: 400 });
  }

  let result;
  let supportResources: string | undefined;
  try {
    ({ result, supportResources } = await recordSessionAnswer({
      id,
      anonymousSessionId,
      assessmentId: session.assessmentId,
      config,
      state,
      expected,
      questionKey,
      selectedOptionKeys,
      scaleValue,
      openText,
      skipped,
      modelConfig,
    }));
  } catch {
    return NextResponse.json({ error: "openText is required" }, { status: 400 });
  }

  if (result.isComplete) {
    await completeAssessmentSession({
      id,
      anonymousSessionId,
      assessmentId: session.assessmentId,
      config,
      state: result.state,
      modelConfig,
    });
  }

  return NextResponse.json({
    nextQuestion: result.nextQuestion ? toClientQuestion(result.nextQuestion) : null,
    isComplete: result.isComplete,
    progress: result.progress,
    supportResources,
  });
}
