import { randomUUID } from "node:crypto";
import { detectTensions, type DimensionState } from "@inner/assessment-engine";
import { generateReport, assembleReportDocument, type ReportContext, type ReportTension, type ReportDocument, type ReportDocumentRecommendation } from "@inner/ai";
import { dimensionPool } from "@inner/content/dimensions";
import { getAssessmentConfig } from "@/lib/assessments";
import { getAiModelConfig } from "@/lib/aiConfig";
import { getPublishedPersona } from "@/lib/promptTemplates";
import { selectRecommendation } from "@/lib/recommendation";

const dimensionLabels = Object.fromEntries(dimensionPool.map((d) => [d.key, d.label]));

export interface ReportPreviewInput {
  assessmentSlug: string;
  sampleProfileKey?: string;
  language?: string;
}

export interface ReportPreviewResult {
  document: ReportDocument;
  assessmentLabel: string;
}

/**
 * Builds a full ReportDocument from synthesized sample evidence — never a
 * real purchase, never a real user's session — so an admin can preview the
 * effect of a template-structure or prompt change before it ever reaches a
 * paying customer. Mirrors lib/admin/promptPlayground.ts's sample-scoring
 * approach but goes all the way through to a real assembled ReportDocument
 * (dimensions, tensions, recommendation, reflection questions) rather than
 * just the raw AI sections.
 */
export async function buildReportPreview(input: ReportPreviewInput): Promise<ReportPreviewResult | { error: string }> {
  const config = await getAssessmentConfig(input.assessmentSlug);
  if (!config) return { error: `Assessment "${input.assessmentSlug}" not found or not loadable` };

  const profile = input.sampleProfileKey ? config.profiles.find((p) => p.key === input.sampleProfileKey) : config.profiles[0];
  if (!profile) return { error: "No sample profile available for this assessment" };

  const dimensionScores: Record<string, number> = {};
  const dimensionConfidence: Record<string, number> = {};
  const dimensionStates: Record<string, DimensionState> = {};
  for (const dim of config.dimensions) {
    const range = profile.matchingRule.dimensionRanges?.[dim.key];
    const normalized = range ? (range[0] + range[1]) / 2 : 50;
    dimensionScores[dim.key] = normalized;
    dimensionConfidence[dim.key] = 0.8;
    dimensionStates[dim.key] = { raw: 0, normalized, confidence: 0.8, consistency: 1 };
  }

  const tensions: ReportTension[] = detectTensions(config, dimensionStates).map((t) => ({ label: t.label, strength: t.strength }));

  const secondaryProfiles = config.profiles.filter((p) => p.key !== profile.key).slice(0, 1);

  const reportContext: ReportContext = {
    assessmentName: config.name,
    assessmentVersion: config.version,
    primaryProfileName: profile.name,
    primaryProfileDescription: profile.descriptionTemplate,
    secondaryProfileNames: secondaryProfiles.map((p) => p.name),
    dimensionScores,
    dimensionConfidence,
    dimensionLabels,
    tensions,
    contradictions: [], // sample data has no real answer history to derive a contradiction from — honestly empty, not faked
    openAnswerThemes: [],
    language: input.language ?? "en",
    reportType: "individual",
    sections: config.premiumReportStructure.map((s) => ({ key: s.key, title: s.title })),
  };

  const [modelConfig, persona, liveRecommendation] = await Promise.all([
    getAiModelConfig(),
    getPublishedPersona(config.slug),
    // A fresh, never-persisted id — selectRecommendation's "already completed" filter always resolves to
    // "nothing completed yet" for it, which is exactly right for a synthetic preview.
    selectRecommendation({ anonymousSessionId: randomUUID(), fromConfig: config, primaryProfileName: profile.name, dimensionScores }),
  ]);

  const generated = await generateReport(reportContext, modelConfig, persona);

  const recommendation: ReportDocumentRecommendation | null = liveRecommendation
    ? { assessmentSlug: liveRecommendation.slug, assessmentName: liveRecommendation.name, bridgeCopy: liveRecommendation.bridgeCopy }
    : null;

  const document = assembleReportDocument({ context: reportContext, generated, assessmentSlug: config.slug, recommendation });

  return { document, assessmentLabel: config.name };
}
