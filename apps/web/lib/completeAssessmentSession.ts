import { prisma } from "@inner/db";
import { computeResult } from "@inner/assessment-engine";
import type { AssessmentConfig, SessionState } from "@inner/assessment-engine";
import { enrichProfileWithAI, generateFreeInsight, type AIModelConfig } from "@inner/ai";
import { dimensionPool } from "@inner/content";
import { track } from "@/lib/analytics";
import { getPublishedPersona } from "@/lib/promptTemplates";
import type { OpenResponseAiMeta } from "@/lib/openResponseAiMeta";

/**
 * Scores the final session state, runs profile/report-input AI enrichment,
 * and persists DimensionScore/ProfileResult + marks the session completed —
 * exactly the completion branch app/api/sessions/[id]/answer/route.ts has
 * always run inline, extracted so the FASE 29 demo persona seeding route
 * (app/api/admin/demo/start/route.ts) can reuse the same real logic instead
 * of duplicating it. Pure relocation — no behavior change.
 */
export async function completeAssessmentSession(params: {
  id: string;
  anonymousSessionId: string;
  assessmentId: string;
  config: AssessmentConfig;
  state: SessionState;
  modelConfig: AIModelConfig;
}): Promise<void> {
  const { id, anonymousSessionId, assessmentId, config, state, modelConfig } = params;

  const { profileResult, dimensionScores, tensions, contradictions } = computeResult(config, state);
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

  await track({ anonymousSessionId, eventName: "assessment_completed", assessmentId });
}
