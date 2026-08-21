import { prisma } from "@inner/db";
import { submitAnswer } from "@inner/assessment-engine";
import type { AnswerResult, AssessmentConfig, Question, SessionState } from "@inner/assessment-engine";
import { chooseFollowup, interpretOpenAnswer, SUPPORT_MESSAGE, type AIModelConfig } from "@inner/ai";
import { encryptText } from "@/lib/security/encryption";
import { track } from "@/lib/analytics";
import type { OpenResponseAiMeta } from "@/lib/openResponseAiMeta";

/**
 * Persists one answer (Response/OpenResponse row + AI interpretation for
 * open_text), advances the engine via submitAnswer, and tracks the
 * corresponding analytics event — the exact per-question logic
 * app/api/sessions/[id]/answer/route.ts has always run inline, extracted so
 * the FASE 29 demo persona seeding route (app/api/admin/demo/start/route.ts)
 * can drive the same real engine + persistence path a genuine user's answers
 * go through, instead of duplicating it. Pure relocation — no behavior
 * change for the live route.
 */
export async function recordSessionAnswer(params: {
  id: string;
  anonymousSessionId: string;
  assessmentId: string;
  config: AssessmentConfig;
  state: SessionState;
  expected: Question;
  questionKey: string;
  selectedOptionKeys?: string[];
  scaleValue?: number;
  openText?: string;
  skipped: boolean;
  modelConfig: AIModelConfig;
  /** FASE 31 §QA SIMULATION — synthetic QA-persona sessions still write real Response rows (so scoring/adaptive behavior is genuinely exercised) but must never inflate real funnel analytics. Defaults to false; every real caller is unaffected. */
  skipAnalytics?: boolean;
}): Promise<{ result: AnswerResult; supportResources?: string }> {
  const {
    id,
    anonymousSessionId,
    assessmentId,
    config,
    state,
    expected,
    questionKey,
    selectedOptionKeys,
    scaleValue,
    openText,
    skipped,
    modelConfig,
    skipAnalytics,
  } = params;

  let aiDimensionNudges: Record<string, number> | undefined;
  let aiChosenFollowupKey: string | undefined;
  let supportResources: string | undefined;

  if (skipped) {
    // "Prefer not to answer" — only offered on questions marked `sensitive`.
    // No AI interpretation call, no stored answer content, just a Response
    // row with nothing selected so the question is never re-asked.
    await prisma.response.create({ data: { assessmentSessionId: id, questionId: questionKey } });
  } else if (expected.type === "open_text") {
    const trimmed = openText?.trim();
    if (!trimmed) throw new Error("openText is required");

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
    selectedOptionKeys: skipped ? undefined : selectedOptionKeys,
    scaleValue: skipped ? undefined : scaleValue,
    openText: skipped ? undefined : openText,
    aiDimensionNudges,
    aiChosenFollowupKey,
    skipped,
  });

  if (!skipAnalytics) {
    await track({
      anonymousSessionId,
      eventName: skipped ? "question_skipped" : expected.type === "open_text" ? "open_answer_submitted" : "question_answered",
      assessmentId,
      properties: { questionKey },
    });
  }

  return { result, supportResources };
}
