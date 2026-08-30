import { prisma } from "@inner/db";
import { startSession, nextQuestion } from "@inner/assessment-engine";
import type { AssessmentConfig, Question } from "@inner/assessment-engine";
import { isAiEnabled } from "@inner/ai";
import { getAssessmentConfig } from "@/lib/assessments";
import { getAiModelConfig } from "@/lib/aiConfig";
import { recordSessionAnswer } from "@/lib/recordSessionAnswer";
import { completeAssessmentSession } from "@/lib/completeAssessmentSession";
import { chooseAnswerForPersona } from "@/lib/demoAnswerSelection";
import { generateQaPersonas } from "@/lib/qa/genericQaPersonas";
import { dimensionPool } from "@inner/content/dimensions";
import type {
  QaResult,
  ProfileDistributionRow,
  DimensionStatsRow,
  RateRow,
  QuestionStatsRow,
  RedundantPairRow,
} from "@/lib/qa/runLoveQaSimulation";

const MAX_STEPS_GUARD = 60;
const HIGH_DISTRIBUTION_FLAG_PCT = 25;
const LOW_DISTRIBUTION_FLAG_PCT = 1;

/** Same structural-redundancy check as runLoveQaSimulation.ts's private helper — duplicated rather than imported/exported across files to keep each simulation module self-contained. */
function findRedundantQuestionPairs(config: AssessmentConfig): RedundantPairRow[] {
  const allQuestions = [...config.questionBank.core, ...config.questionBank.adaptivePool];
  const signatures = allQuestions
    .filter((q) => q.options && q.options.length > 0)
    .map((q) => {
      const dims = new Set<string>();
      for (const opt of q.options ?? []) {
        for (const dim of Object.keys(opt.dimensionContributions)) dims.add(dim);
      }
      return { question: q, dims };
    })
    .filter((s) => s.dims.size > 0);

  const pairs: RedundantPairRow[] = [];
  for (let i = 0; i < signatures.length; i++) {
    for (let j = i + 1; j < signatures.length; j++) {
      const a = signatures[i];
      const b = signatures[j];
      if (a.dims.size !== b.dims.size) continue;
      const shared = [...a.dims].filter((d) => b.dims.has(d));
      if (shared.length === a.dims.size && shared.length > 0) {
        pairs.push({ a: a.question.key, aPrompt: a.question.prompt, b: b.question.key, bPrompt: b.question.prompt, sharedDimensions: shared });
      }
    }
  }
  return pairs;
}

/**
 * §GENERIC 100-PERSONA QA SIMULATION — assessment-agnostic sibling of
 * lib/qa/runLoveQaSimulation.ts (FASE 31), built to extend the same QA
 * process to the other 9 assessments now that LOVE has been soft-launched
 * and validated (FASE 33). Deliberately does NOT touch runLoveQaSimulation.ts
 * or loveQaPersonas.ts — LOVE keeps its exact original, hand-tuned QA code
 * path so its existing run history stays a fair apples-to-apples comparison
 * against future LOVE re-runs. This module reimplements the same aggregation
 * logic parametrized by `slug`, driving personas from the generic,
 * dimension-agnostic generator in lib/qa/genericQaPersonas.ts.
 *
 * Same honesty constraint as the LOVE version: AI-dependent quality checks
 * are not fabricated here. With no ANTHROPIC_API_KEY configured, every AI
 * call falls back to identical static content regardless of persona, so
 * `aiWasEnabled` records which case a given run is instead of presenting a
 * fabricated pass.
 */
export async function runAssessmentQaSimulation(slug: string, count = 100): Promise<QaResult> {
  const config = await getAssessmentConfig(slug);
  if (!config) throw new Error(`Assessment "${slug}" is not available`);

  const assessment = await prisma.assessment.findUnique({ where: { slug } });
  if (!assessment) throw new Error(`Assessment "${slug}" is not seeded`);

  const version = await prisma.assessmentVersion.findFirst({
    where: { assessmentId: assessment.id, publishedAt: { not: null } },
    orderBy: { versionNumber: "desc" },
  });
  if (!version) throw new Error(`Assessment "${slug}" has no published version`);

  const modelConfig = await getAiModelConfig();
  const dimensionKeys = config.dimensions.map((d) => d.key);
  const personas = generateQaPersonas(dimensionKeys, count);

  const profileCounts = new Map<string, { name: string; count: number }>();
  const dimensionValues = new Map<string, number[]>();
  const tensionCounts = new Map<string, string>();
  const tensionFireCounts = new Map<string, number>();
  const contradictionFireCounts = new Map<string, number>();
  const questionAskedCounts = new Map<string, number>();
  const questionMeta = new Map<string, Question>();
  const questionOptionCounts = new Map<string, Map<string, number>>();
  let totalQuestionsAsked = 0;
  let completedSessions = 0;

  for (const persona of personas) {
    const anon = await prisma.anonymousSession.create({
      data: { firstLandingSlug: slug, utmSource: "qa_simulation", utmCampaign: persona.key },
    });
    const session = await prisma.assessmentSession.create({
      data: { anonymousSessionId: anon.id, assessmentId: assessment.id, assessmentVersionId: version.id, sourceSlug: slug },
    });

    let state = startSession(config);
    for (let step = 0; step < MAX_STEPS_GUARD; step++) {
      const question = nextQuestion(config, state);
      if (!question) break;

      questionMeta.set(question.key, question);
      questionAskedCounts.set(question.key, (questionAskedCounts.get(question.key) ?? 0) + 1);

      const answer = chooseAnswerForPersona(question, persona, state);
      if (answer.selectedOptionKeys) {
        const optMap = questionOptionCounts.get(question.key) ?? new Map<string, number>();
        for (const key of answer.selectedOptionKeys) optMap.set(key, (optMap.get(key) ?? 0) + 1);
        questionOptionCounts.set(question.key, optMap);
      }

      const { result } = await recordSessionAnswer({
        id: session.id,
        anonymousSessionId: anon.id,
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
        skipAnalytics: true,
      });
      state = result.state;
      totalQuestionsAsked++;

      if (result.isComplete) {
        const computed = await completeAssessmentSession({
          id: session.id,
          anonymousSessionId: anon.id,
          assessmentId: assessment.id,
          config,
          state,
          modelConfig,
          skipAnalytics: true,
        });
        completedSessions++;

        const primary = computed.profileResult.primary;
        const existing = profileCounts.get(primary.key);
        profileCounts.set(primary.key, { name: primary.name, count: (existing?.count ?? 0) + 1 });

        for (const [dimKey, score] of Object.entries(computed.dimensionScores)) {
          const arr = dimensionValues.get(dimKey) ?? [];
          arr.push(score.normalized);
          dimensionValues.set(dimKey, arr);
        }

        for (const t of computed.tensions) {
          tensionCounts.set(t.key, t.label);
          tensionFireCounts.set(t.key, (tensionFireCounts.get(t.key) ?? 0) + 1);
        }
        for (const c of computed.contradictions) {
          contradictionFireCounts.set(c.dimensionKey, (contradictionFireCounts.get(c.dimensionKey) ?? 0) + 1);
        }
        break;
      }
    }
  }

  const dimensionLabelByKey = Object.fromEntries(dimensionPool.map((d) => [d.key, d.label]));

  const profileDistribution: ProfileDistributionRow[] = [...profileCounts.entries()]
    .map(([profileKey, { name, count }]): ProfileDistributionRow => {
      const pct = Math.round((count / completedSessions) * 1000) / 10;
      const flag: ProfileDistributionRow["flag"] =
        pct > HIGH_DISTRIBUTION_FLAG_PCT ? "too_common" : pct < LOW_DISTRIBUTION_FLAG_PCT ? "too_rare" : null;
      return { profileKey, profileName: name, count, pct, flag };
    })
    .sort((a, b) => b.count - a.count);

  for (const profile of config.profiles) {
    if (!profileCounts.has(profile.key)) {
      profileDistribution.push({ profileKey: profile.key, profileName: profile.name, count: 0, pct: 0, flag: "too_rare" });
    }
  }

  const dimensionStats: DimensionStatsRow[] = config.dimensions.map((d) => {
    const values = dimensionValues.get(d.key) ?? [];
    return {
      key: d.key,
      label: dimensionLabelByKey[d.key] ?? d.key,
      min: values.length ? Math.round(Math.min(...values)) : 0,
      max: values.length ? Math.round(Math.max(...values)) : 0,
      avg: values.length ? Math.round((values.reduce((s, v) => s + v, 0) / values.length) * 10) / 10 : 0,
    };
  });

  const tensionFiringRates: RateRow[] = [...tensionCounts.entries()].map(([key, label]) => ({
    key,
    label,
    firedCount: tensionFireCounts.get(key) ?? 0,
    pct: Math.round(((tensionFireCounts.get(key) ?? 0) / completedSessions) * 1000) / 10,
  }));

  const contradictionFiringRates: RateRow[] = [...contradictionFireCounts.entries()].map(([dimensionKey, firedCount]) => ({
    key: dimensionKey,
    label: dimensionLabelByKey[dimensionKey] ?? dimensionKey,
    firedCount,
    pct: Math.round((firedCount / completedSessions) * 1000) / 10,
  }));

  const questionStats: QuestionStatsRow[] = [...questionMeta.entries()].map(([key, question]) => {
    const timesAsked = questionAskedCounts.get(key) ?? 0;
    const optMap = questionOptionCounts.get(key);
    const optionDistribution = optMap
      ? [...optMap.entries()]
          .map(([optionKey, count]) => ({
            optionKey,
            label: question.options?.find((o) => o.key === optionKey)?.label ?? optionKey,
            count,
            pct: Math.round((count / timesAsked) * 1000) / 10,
          }))
          .sort((a, b) => b.count - a.count)
      : null;
    return {
      key,
      prompt: question.prompt,
      type: question.type,
      isCore: question.isCore,
      timesAsked,
      askedPct: Math.round((timesAsked / personas.length) * 1000) / 10,
      optionDistribution,
    };
  });

  return {
    runAt: new Date().toISOString(),
    assessmentSlug: slug,
    personaCount: personas.length,
    averageQuestionsPerSession: Math.round((totalQuestionsAsked / Math.max(1, completedSessions)) * 10) / 10,
    profileDistribution,
    dimensionStats,
    tensionFiringRates,
    contradictionFiringRates,
    questionStats: questionStats.sort((a, b) => b.timesAsked - a.timesAsked),
    redundantQuestionPairs: findRedundantQuestionPairs(config),
    aiWasEnabled: isAiEnabled(),
  };
}
