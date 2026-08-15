import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { computeResult, nextQuestion, submitAnswer } from "@inner/assessment-engine";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { reconstructSessionState } from "@/lib/sessionState";
import { encryptText } from "@/lib/security/encryption";
import { toClientQuestion } from "@/lib/clientQuestion";
import { track } from "@/lib/analytics";

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

  const config = getAssessmentConfig(session.sourceSlug);
  if (!config) return NextResponse.json({ error: "Unknown assessment" }, { status: 500 });

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

  if (expected.type === "open_text") {
    if (!openText?.trim()) return NextResponse.json({ error: "openText is required" }, { status: 400 });
    await prisma.openResponse.create({
      data: {
        assessmentSessionId: id,
        questionId: questionKey,
        rawTextEncrypted: encryptText(openText.trim()),
      },
    });
  } else {
    await prisma.response.create({
      data: {
        assessmentSessionId: id,
        questionId: questionKey,
        selectedOptionIds: selectedOptionKeys ?? undefined,
        scaleValue: scaleValue ?? undefined,
      },
    });
  }

  await prisma.assessmentSession.update({ where: { id }, data: { questionCount: { increment: 1 } } });

  const result = submitAnswer(config, state, { questionKey, selectedOptionKeys, scaleValue, openText });

  await track({
    anonymousSessionId,
    eventName: expected.type === "open_text" ? "open_answer_submitted" : "question_answered",
    assessmentId: session.assessmentId,
    properties: { questionKey },
  });

  if (result.isComplete) {
    const { profileResult, dimensionScores } = computeResult(config, result.state);

    await prisma.$transaction([
      ...Object.entries(dimensionScores).map(([dimensionKey, score]) =>
        prisma.dimensionScore.upsert({
          where: { assessmentSessionId_dimensionKey: { assessmentSessionId: id, dimensionKey } },
          update: { rawScore: score.raw, normalizedScore: score.normalized, confidence: score.confidence },
          create: {
            assessmentSessionId: id,
            dimensionKey,
            rawScore: score.raw,
            normalizedScore: score.normalized,
            confidence: score.confidence,
          },
        })
      ),
      prisma.profileResult.upsert({
        where: { assessmentSessionId: id },
        update: {
          primaryProfileKey: profileResult.primary.key,
          secondaryProfileKeys: profileResult.secondary.map((p) => p.key),
        },
        create: {
          assessmentSessionId: id,
          primaryProfileKey: profileResult.primary.key,
          secondaryProfileKeys: profileResult.secondary.map((p) => p.key),
        },
      }),
      prisma.assessmentSession.update({ where: { id }, data: { status: "completed", completedAt: new Date() } }),
    ]);

    await track({ anonymousSessionId, eventName: "assessment_completed", assessmentId: session.assessmentId });
  }

  return NextResponse.json({
    nextQuestion: result.nextQuestion ? toClientQuestion(result.nextQuestion) : null,
    isComplete: result.isComplete,
    progress: result.progress,
  });
}
