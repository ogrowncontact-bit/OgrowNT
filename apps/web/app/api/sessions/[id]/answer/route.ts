import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { computeResult, nextQuestion, submitAnswer } from "@inner/assessment-engine";
import { chooseFollowup, enrichProfileWithAI, generateFreeInsight, interpretOpenAnswer, SUPPORT_MESSAGE } from "@inner/ai";
import { dimensionPool } from "@inner/content";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { reconstructSessionState } from "@/lib/sessionState";
import { encryptText } from "@/lib/security/encryption";
import { toClientQuestion } from "@/lib/clientQuestion";
import { track } from "@/lib/analytics";
import type { OpenResponseAiMeta } from "@/lib/openResponseAiMeta";
import { ensureAiTelemetryRegistered } from "@/lib/aiTelemetry";
import { getAiModelConfig } from "@/lib/aiConfig";
import { getPublishedPersona } from "@/lib/promptTemplates";

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

  let aiDimensionNudges: Record<string, number> | undefined;
  let aiChosenFollowupKey: string | undefined;
  let supportResources: string | undefined;

  if (expected.type === "open_text") {
    const trimmed = openText?.trim();
    if (!trimmed) return NextResponse.json({ error: "openText is required" }, { status: 400 });

    const analysis = await interpretOpenAnswer(
      {
        questionPrompt: expected.prompt,
        answerText: trimmed,
        allowedDimensions: config.dimensions.map((d) => d.key),
      },
      modelConfig
    );

    // Question AI only gets to choose among candidates this question actually
    // declares, and only ones not already asked in this session (§4/§5).
    const unusedCandidates = (expected.dynamicFollowupCandidates ?? [])
      .filter((key) => !state.askedQuestionKeys.includes(key))
      .map((key) => {
        const q = config.questionBank.adaptivePool.find((q) => q.key === key);
        return q ? { key: q.key, prompt: q.prompt } : null;
      })
      .filter((c): c is { key: string; prompt: string } => c !== null);

    if (unusedCandidates.length > 0) {
      const choice = await chooseFollowup({ answerText: trimmed, tags: analysis.tags, candidates: unusedCandidates }, modelConfig);
      aiChosenFollowupKey = choice.chosenKey ?? undefined;
    }

    aiDimensionNudges = analysis.dimensionNudges;
    if (analysis.safetyFlag) supportResources = SUPPORT_MESSAGE;

    const meta: OpenResponseAiMeta = {
      tags: analysis.tags,
      sentiment: analysis.sentiment,
      dimensionNudges: analysis.dimensionNudges,
      chosenFollowupKey: aiChosenFollowupKey,
      aiGenerated: analysis.aiGenerated,
      confidence: analysis.confidence,
    };

    await prisma.openResponse.create({
      data: {
        assessmentSessionId: id,
        questionId: questionKey,
        rawTextEncrypted: encryptText(trimmed),
        aiTags: meta as any,
        aiSentiment: analysis.sentiment,
        safetyFlag: analysis.safetyFlag,
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

  const result = submitAnswer(config, state, {
    questionKey,
    selectedOptionKeys,
    scaleValue,
    openText,
    aiDimensionNudges,
    aiChosenFollowupKey,
  });

  await track({
    anonymousSessionId,
    eventName: expected.type === "open_text" ? "open_answer_submitted" : "question_answered",
    assessmentId: session.assessmentId,
    properties: { questionKey },
  });

  if (result.isComplete) {
    const { profileResult, dimensionScores, tensions, contradictions } = computeResult(config, result.state);
    const persona = await getPublishedPersona(config.slug);

    // Profile AI only narrates the profile the deterministic matcher already
    // picked (§6) — collected tags come from this session's own open answers.
    const openResponses = await prisma.openResponse.findMany({ where: { assessmentSessionId: id } });
    const openAnswerTags = openResponses.flatMap((r) => (r.aiTags as OpenResponseAiMeta | null)?.tags ?? []);

    const generatedInsight = await generateFreeInsight(
      {
        primaryProfileName: profileResult.primary.name,
        primaryProfileDescription: profileResult.primary.descriptionTemplate,
        dimensionScores: Object.fromEntries(Object.entries(dimensionScores).map(([k, v]) => [k, v.normalized])),
        openAnswerTags,
      },
      modelConfig
    );

    const contradictionInputs = contradictions.map((c) => ({
      dimensionKey: c.dimensionKey,
      label: dimensionPool.find((d) => d.key === c.dimensionKey)?.label ?? c.dimensionKey,
      strength: 1 - c.consistency,
    }));

    // REPORT INPUT stage: enriches the already-decided profile/tensions/
    // contradictions with themes and narrative insights for the future
    // premium report. Never the decision-maker — profileResult/tensions/
    // contradictions above are already final by the time this runs. Always
    // resolves to *something* structured, AI or not.
    const enrichment = await enrichProfileWithAI(
      {
        assessmentSlug: config.slug,
        assessmentVersion: config.version,
        primaryProfileName: profileResult.primary.name,
        secondaryProfileNames: profileResult.secondary.map((p) => p.name),
        dimensions: Object.entries(dimensionScores).map(([key, score]) => ({
          key,
          label: dimensionPool.find((d) => d.key === key)?.label ?? key,
          normalized: score.normalized,
          confidence: score.confidence,
        })),
        tensions,
        contradictions: contradictionInputs,
        openAnswerThemes: openAnswerTags,
      },
      modelConfig,
      persona
    );

    const aiSemanticNotes = {
      insight: generatedInsight?.insight,
      aiGenerated: generatedInsight ? true : undefined,
      themes: enrichment.themes,
      insights: enrichment.insights,
      enrichmentAiGenerated: enrichment.aiGenerated,
    };

    await prisma.$transaction([
      ...Object.entries(dimensionScores).map(([dimensionKey, score]) =>
        prisma.dimensionScore.upsert({
          where: { assessmentSessionId_dimensionKey: { assessmentSessionId: id, dimensionKey } },
          update: { rawScore: score.raw, normalizedScore: score.normalized, confidence: score.confidence, consistency: score.consistency },
          create: {
            assessmentSessionId: id,
            dimensionKey,
            rawScore: score.raw,
            normalizedScore: score.normalized,
            confidence: score.confidence,
            consistency: score.consistency,
          },
        })
      ),
      prisma.profileResult.upsert({
        where: { assessmentSessionId: id },
        update: {
          primaryProfileKey: profileResult.primary.key,
          secondaryProfileKeys: profileResult.secondary.map((p) => p.key),
          tensions: tensions as any,
          contradictions: contradictions as any,
          aiSemanticNotes: aiSemanticNotes as any,
        },
        create: {
          assessmentSessionId: id,
          primaryProfileKey: profileResult.primary.key,
          secondaryProfileKeys: profileResult.secondary.map((p) => p.key),
          tensions: tensions as any,
          contradictions: contradictions as any,
          aiSemanticNotes: aiSemanticNotes as any,
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
    supportResources,
  });
}
