import type { GenerateReportResult, GeneratedReportSection, ReportContext } from "./reportAI";
import { sectionObjectiveFor, type SectionRole } from "./promptEngine";

export interface ReportDocumentSection extends GeneratedReportSection {
  /** How this section should be visually treated — a card, a callout, a plain paragraph, etc. Derived from the section key, never re-decided per report. */
  role: SectionRole;
}

export interface ReportDocumentDimension {
  key: string;
  label: string;
  normalized: number;
  confidence: number;
}

export interface ReportDocumentRecommendation {
  assessmentSlug: string;
  assessmentName: string;
  bridgeCopy: string;
}

export interface ReportDocumentMeta {
  assessmentName: string;
  assessmentSlug: string;
  assessmentVersion: number;
  reportEngineVersion: number;
  promptVersion: number;
  personaVersion: number;
  modelVersion: string;
  language: string;
  generatedAt: string; // ISO
}

/**
 * The single structured shape both the web report page and the PDF
 * renderer consume — neither one has its own separate logic for turning
 * scores/sections into a layout. `sections` stays the canonical narrative
 * content (role-tagged rather than duplicated into separate "strengths"/
 * "tensions" arrays — see docs/ARCHITECTURE.md §7's note on avoiding
 * repeating the same idea in multiple places): a renderer picks visual
 * treatment per role (card, callout, plain paragraph) rather than the
 * document repeating each observation once as a "what stands out" teaser
 * and again as its own dedicated section.
 */
export interface ReportDocument {
  meta: ReportDocumentMeta;
  profile: { name: string; description: string; secondaryNames: string[] };
  /** One short "what did INNER learn" opener — reused directly from the signature section, never a second AI call. */
  summary: string;
  dimensions: ReportDocumentDimension[];
  sections: ReportDocumentSection[];
  reflectionQuestions: string[];
  recommendation: ReportDocumentRecommendation | null;
}

export interface AssembleReportDocumentParams {
  context: ReportContext;
  generated: GenerateReportResult;
  assessmentSlug: string;
  recommendation: ReportDocumentRecommendation | null;
  generatedAt?: Date;
}

export function assembleReportDocument(params: AssembleReportDocumentParams): ReportDocument {
  const { context, generated, assessmentSlug, recommendation } = params;

  const sections: ReportDocumentSection[] = generated.sections.map((s) => ({
    ...s,
    role: sectionObjectiveFor(s.key, s.title).role,
  }));

  const signatureSection = sections.find((s) => s.role === "signature");
  const summary = signatureSection?.body || context.primaryProfileDescription;

  const dimensions: ReportDocumentDimension[] = Object.entries(context.dimensionScores).map(([key, normalized]) => ({
    key,
    label: context.dimensionLabels[key] ?? key,
    normalized,
    confidence: context.dimensionConfidence[key] ?? 0,
  }));

  return {
    meta: {
      assessmentName: context.assessmentName,
      assessmentSlug,
      assessmentVersion: context.assessmentVersion,
      reportEngineVersion: generated.reportEngineVersion,
      promptVersion: generated.promptVersion,
      personaVersion: generated.personaVersion,
      modelVersion: generated.modelVersion,
      language: generated.language,
      generatedAt: (params.generatedAt ?? new Date()).toISOString(),
    },
    profile: {
      name: context.primaryProfileName,
      description: context.primaryProfileDescription,
      secondaryNames: context.secondaryProfileNames,
    },
    summary,
    dimensions,
    sections,
    reflectionQuestions: generated.reflectionQuestions,
    recommendation,
  };
}
