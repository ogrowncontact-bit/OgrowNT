import { prisma } from "@inner/db";
import { generateReport, type ReportContext, type AssessmentPersona } from "@inner/ai";
import { getAssessmentConfig } from "@/lib/assessments";
import { getAiModelConfig } from "@/lib/aiConfig";
import { dimensionPool } from "@inner/content/dimensions";

const dimensionLabels = Object.fromEntries(dimensionPool.map((d) => [d.key, d.label]));

export interface PlaygroundInput {
  promptTemplateId: string;
  sampleProfileKey?: string;
  /** Comma-separated sample theme tags, standing in for "sample answers" — never raw open-text, matching the real pipeline's own evidence-minimization rule. */
  sampleThemes?: string;
  language?: string;
}

export interface PlaygroundResult {
  assessmentSlug: string;
  personaName: string;
  personaVersion: number;
  personaStatus: string;
  sampleProfileName: string;
  sampleDimensionScores: Record<string, number>;
  result: Awaited<ReturnType<typeof generateReport>>;
}

/**
 * Synthesizes sample evidence directly from the assessment's own config
 * (never a real user's session) and runs the real generateReport()
 * pipeline with the chosen — possibly still-draft — persona, so an admin
 * can preview a prompt's effect before publishing it. Never exposes an API
 * key; this route is admin-auth-gated, same as the rest of /admin.
 */
export async function runPromptPlayground(input: PlaygroundInput): Promise<PlaygroundResult | { error: string }> {
  const template = await prisma.promptTemplate.findUnique({ where: { id: input.promptTemplateId } });
  if (!template) return { error: "Prompt template not found" };

  const config = await getAssessmentConfig(template.assessmentSlug);
  if (!config) return { error: `Assessment "${template.assessmentSlug}" not found or not loadable` };

  const profile = input.sampleProfileKey
    ? config.profiles.find((p) => p.key === input.sampleProfileKey)
    : config.profiles[0];
  if (!profile) return { error: "No sample profile available for this assessment" };

  // Midpoint of this profile's own matching ranges — a plausible, specific
  // sample rather than a flat 50 everywhere, so the playground actually
  // exercises the "connect two dimensions" instruction.
  const dimensionScores: Record<string, number> = {};
  const dimensionConfidence: Record<string, number> = {};
  for (const dim of config.dimensions) {
    const range = profile.matchingRule.dimensionRanges?.[dim.key];
    dimensionScores[dim.key] = range ? (range[0] + range[1]) / 2 : 50;
    dimensionConfidence[dim.key] = 0.8;
  }

  const persona: AssessmentPersona = {
    assessmentSlug: template.assessmentSlug,
    name: template.personaName,
    focus: template.personaFocus,
    prompt: template.personaPrompt,
    tone: { warmth: template.toneWarmth, directness: template.toneDirectness, depth: template.toneDepth, formality: template.toneFormality },
    version: template.version,
  };

  const reportContext: ReportContext = {
    assessmentName: config.name,
    assessmentVersion: config.version,
    primaryProfileName: profile.name,
    primaryProfileDescription: profile.descriptionTemplate,
    secondaryProfileNames: [],
    dimensionScores,
    dimensionConfidence,
    dimensionLabels,
    tensions: [],
    contradictions: [],
    openAnswerThemes: (input.sampleThemes ?? "").split(",").map((t) => t.trim()).filter(Boolean),
    language: input.language ?? "en",
    reportType: "individual",
    sections: config.premiumReportStructure.map((s) => ({ key: s.key, title: s.title })),
  };

  const modelConfig = await getAiModelConfig();
  const result = await generateReport(reportContext, modelConfig, persona);

  return {
    assessmentSlug: template.assessmentSlug,
    personaName: template.personaName,
    personaVersion: template.version,
    personaStatus: template.status,
    sampleProfileName: profile.name,
    sampleDimensionScores: dimensionScores,
    result,
  };
}
