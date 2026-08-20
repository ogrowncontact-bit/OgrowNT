import { callStructured, isAiEnabled } from "./client";
import { enforceNonDiagnostic } from "./guardrails/nonDiagnosticFilter";
import { validateReportQuality } from "./reportQualityValidator";
import { resolveModelConfig, type AIModelConfig } from "./modelConfig";
import { bucketConfidence } from "./confidence";

export interface ReportSectionSpec {
  key: string;
  title: string;
}

export interface GeneratedReportSection {
  key: string;
  title: string;
  body: string;
  aiGenerated: boolean;
}

export interface ReportTension {
  label: string;
  strength: number; // 0..1
}

export interface ReportContradiction {
  label: string;
  /** 0..1 — how strongly the contributing answers disagreed in direction. */
  strength: number;
}

export const REPORT_ENGINE_VERSION = 1;
export const REPORT_PROMPT_VERSION = 2; // bumped alongside the system prompt below

export const SUPPORTED_REPORT_LANGUAGES = ["en", "es", "pt"] as const;
export type ReportLanguage = (typeof SUPPORTED_REPORT_LANGUAGES)[number];
// Architecture-ready, not yet wired to real generation — see generateReport()'s language handling.
export const PLANNED_REPORT_LANGUAGES = ["fr", "it", "de", "nl"] as const;

const LANGUAGE_NAMES: Record<ReportLanguage, string> = { en: "English", es: "Spanish", pt: "Portuguese" };

/**
 * Normalized input to report generation — the "only what's needed, nothing
 * raw" boundary between the app's DB layer and the AI. Every field here is
 * already a structured, deterministic fact (a score, a label, a tag) — never
 * a raw open-text answer. See docs/ARCHITECTURE.md §7.
 */
export interface ReportContext {
  assessmentName: string;
  assessmentVersion: number;
  primaryProfileName: string;
  primaryProfileDescription: string;
  secondaryProfileNames: string[];
  dimensionScores: Record<string, number>; // key -> normalized 0-100
  dimensionConfidence: Record<string, number>; // key -> 0..1
  dimensionLabels: Record<string, string>;
  tensions: ReportTension[];
  /** Distinct from tensions: two DIFFERENT questions pulling the same dimension in opposite directions. */
  contradictions: ReportContradiction[];
  /** Already-extracted tags from this session's open-text answers (Response AI) — never raw answer text. */
  openAnswerThemes: string[];
  /** ISO 639-1 code. Falls back to "en" generation if unsupported — see generateReport(). */
  language: string;
  reportType: "individual" | "deep";
  sections: ReportSectionSpec[];
}

function resolvedLanguage(language: string): ReportLanguage {
  return (SUPPORTED_REPORT_LANGUAGES as readonly string[]).includes(language) ? (language as ReportLanguage) : "en";
}

function humanize(key: string, labels?: Record<string, string>): string {
  return labels?.[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Shared by the AI prompt and the deterministic fallback, so "strong"/"friction" mean the same thing in both paths. */
export function deriveStrengthsAndFriction(
  dimensionScores: Record<string, number>,
  dimensionLabels?: Record<string, string>
): { strengths: string[]; friction: string[] } {
  const sorted = Object.entries(dimensionScores).sort((a, b) => b[1] - a[1]);
  return {
    strengths: sorted.filter(([, score]) => score >= 65).slice(0, 3).map(([k]) => humanize(k, dimensionLabels)),
    friction: sorted.filter(([, score]) => score <= 35).slice(0, 3).map(([k]) => humanize(k, dimensionLabels)),
  };
}

export interface GenerateReportResult {
  sections: GeneratedReportSection[];
  language: ReportLanguage;
  reportEngineVersion: number;
  promptVersion: number;
  modelVersion: string;
}

/**
 * Generates every premiumReportStructure section in one call (cheaper/
 * faster than one call per section) — each section's output is
 * independently checked against the non-diagnostic filter, and only the
 * sections that fail fall back to the deterministic template, so one bad
 * section never sinks the whole report. Two users with the same primary
 * profile get different reports because dimension scores, tensions, and
 * open-answer themes are never identical — the prompt is built from those,
 * not from the profile name alone. See docs/ARCHITECTURE.md §7.
 */
export async function generateReport(context: ReportContext, modelConfig?: Partial<AIModelConfig>): Promise<GenerateReportResult> {
  const config = resolveModelConfig(modelConfig);
  const language = resolvedLanguage(context.language);
  const modelVersion = config.qualityModel;

  if (!isAiEnabled()) {
    return {
      sections: buildFallbackSections(context),
      language,
      reportEngineVersion: REPORT_ENGINE_VERSION,
      promptVersion: REPORT_PROMPT_VERSION,
      modelVersion: "none",
    };
  }

  const scoreLines = Object.entries(context.dimensionScores)
    .map(([dim, score]) => {
      const confidence = context.dimensionConfidence[dim];
      const confidenceNote = confidence !== undefined ? `, confidence ${confidence.toFixed(2)} (${bucketConfidence(confidence)})` : "";
      return `${humanize(dim, context.dimensionLabels)}: ${Math.round(score)}/100${confidenceNote}`;
    })
    .join(", ");
  const tensionLines = context.tensions.length
    ? context.tensions.map((t) => `${t.label} (strength ${t.strength.toFixed(2)})`).join("; ")
    : "(none detected)";
  const contradictionLines = context.contradictions.length
    ? context.contradictions.map((c) => `${c.label} (strength ${c.strength.toFixed(2)})`).join("; ")
    : "(none detected)";
  const { strengths, friction } = deriveStrengthsAndFriction(context.dimensionScores, context.dimensionLabels);

  const languageInstruction =
    language === "en"
      ? ""
      : ` Write the ENTIRE report naturally in ${LANGUAGE_NAMES[language]}, as a native speaker would write it — never a mechanical word-for-word translation from English.`;

  const result = await callStructured<Record<string, string>>({
    module: "reportAI",
    model: modelVersion,
    system:
      "You write a premium, warm, specific personal-reflection report for a self-reflection app. The " +
      "person's dominant pattern, secondary patterns, and any tensions or contradictions have ALREADY been " +
      "determined by a separate deterministic scoring system — you are narrating and connecting them section " +
      "by section, never diagnosing anything new, inventing a score, or contradicting the given profile. Each " +
      "section is 2-4 sentences, specific to their actual scores and any detected tension or contradiction " +
      "(reference dimensions by name where natural, and connect two dimensions together rather than " +
      "describing them in isolation — e.g. 'your high X paired with your high Y suggests...' is far better " +
      "than two separate generic sentences). If a contradiction is given, weave it in with context-aware, " +
      "situational language — e.g. 'you may be emotionally open when you feel safe, but become more private " +
      "under pressure' — never as a flaw, inconsistency, or unreliability in what they told you. Never write " +
      "generic filler that would apply to anyone with this profile name. Use hedged language throughout: " +
      "'your responses suggest...', 'you appear to...', 'one pattern is...', 'in situations where...'. Never " +
      "say 'you are' or 'you have' as a bare claim, never claim certainty, never predict the future, never " +
      "claim to know unconscious motives, and never use clinical/diagnostic terms (disorder, syndrome, " +
      "diagnosis, trauma, narcissistic, codependent, pathological, etc)." +
      languageInstruction,
    userMessage:
      `Assessment: ${context.assessmentName} (v${context.assessmentVersion})\n` +
      `Primary pattern: ${context.primaryProfileName} — ${context.primaryProfileDescription}\n` +
      `Secondary patterns: ${context.secondaryProfileNames.join(", ") || "(none)"}\n` +
      `Dimension scores: ${scoreLines}\n` +
      `Detected tensions (two strong tendencies coexisting, not a contradiction): ${tensionLines}\n` +
      `Detected contradictions (answers to different questions disagreeing — describe as context-dependent, not as a flaw): ${contradictionLines}\n` +
      `Notable strengths: ${strengths.join(", ") || "(none standout)"}\n` +
      `Notable friction points: ${friction.join(", ") || "(none standout)"}\n` +
      `Themes from their own words: ${context.openAnswerThemes.join(", ") || "(none)"}\n\n` +
      `Write one section for each of:\n${context.sections.map((s) => `- ${s.key}: "${s.title}"`).join("\n")}`,
    toolName: "write_report",
    toolDescription: "Record the report, one body per section key.",
    inputSchema: {
      type: "object",
      properties: Object.fromEntries(context.sections.map((s) => [s.key, { type: "string", maxLength: 900 }])),
      required: context.sections.map((s) => s.key),
    },
    maxTokens: 3000,
    ceilingTokens: config.maxTokens,
    temperature: config.temperature,
    timeoutMs: config.timeoutMs,
  });

  const fallback = buildFallbackSections(context);
  if (!result.ok) {
    return { sections: fallback, language, reportEngineVersion: REPORT_ENGINE_VERSION, promptVersion: REPORT_PROMPT_VERSION, modelVersion };
  }

  let sections = context.sections.map((spec, i) => {
    const raw = result.data[spec.key];
    if (typeof raw !== "string" || !raw.trim()) return fallback[i];
    const filtered = enforceNonDiagnostic(raw.trim());
    if (!filtered.ok) return fallback[i]; // that section falls back; the rest of the report is unaffected
    return { key: spec.key, title: spec.title, body: filtered.text, aiGenerated: true };
  });

  // Second, independent quality gate on the assembled report (per-section
  // non-diagnostic filtering already ran above) — swap any section flagged
  // with a section-specific issue for its deterministic counterpart, rather
  // than paying for a full regeneration. See reportQualityValidator.ts.
  const quality = validateReportQuality({
    sections,
    expectedSectionKeys: context.sections.map((s) => s.key),
    dimensionLabels: Object.values(context.dimensionLabels),
    primaryProfileName: context.primaryProfileName,
    language,
  });
  if (quality.issues.length > 0) {
    const flaggedSectionKeys = new Set(quality.issues.map((i) => i.sectionKey).filter((k): k is string => !!k));
    if (flaggedSectionKeys.size > 0) {
      const fallbackByKey = new Map(fallback.map((s) => [s.key, s]));
      sections = sections.map((s) => (flaggedSectionKeys.has(s.key) ? (fallbackByKey.get(s.key) ?? s) : s));
    }
  }

  return { sections, language, reportEngineVersion: REPORT_ENGINE_VERSION, promptVersion: REPORT_PROMPT_VERSION, modelVersion };
}

/**
 * Deterministic, dimension-driven fallback — works for any assessment's
 * report structure without assessment-specific code, and is what every
 * report is built from when AI is unavailable or a section fails
 * validation. Not as rich as a real generation, but never empty and never
 * generic-feeling: it's parameterized by this session's actual scores, and
 * — unlike the AI path — always in English (see language handling note on
 * generateReport()); a non-English fallback is a known limitation until a
 * template is authored per language.
 */
function buildFallbackSections(context: ReportContext): GeneratedReportSection[] {
  const entries = Object.entries(context.dimensionScores);
  const sorted = [...entries].sort((a, b) => b[1] - a[1]);
  const top = sorted[0];
  const bottom = sorted[sorted.length - 1];
  const { strengths, friction } = deriveStrengthsAndFriction(context.dimensionScores, context.dimensionLabels);
  const topLabel = top ? humanize(top[0], context.dimensionLabels) : "your dominant pattern";
  const topTension = context.tensions[0];
  const topContradiction = context.contradictions[0];

  const byKey: Record<string, string> = {
    signature: `Your INNER Signature: ${context.primaryProfileName}. ${context.primaryProfileDescription}`,
    dominant_pattern: top
      ? `Your responses point most strongly toward ${topLabel} (${Math.round(top[1])}/100), which shapes much of how ${context.primaryProfileName.toLowerCase()} shows up for you day to day.`
      : context.primaryProfileDescription,
    how_you_connect: `Your responses suggest a connection style shaped by where ${topLabel.toLowerCase()} sits for you — this tends to influence how quickly you let people in and how you respond once they're close.`,
    how_you_handle_closeness: `As closeness builds, your responses suggest you notice it most through ${topLabel.toLowerCase()} — how strongly that pattern is present tends to shape whether closeness feels steady or unsettling.`,
    your_independence: context.dimensionScores.independence !== undefined
      ? `Your independence score (${Math.round(context.dimensionScores.independence)}/100) suggests ${context.dimensionScores.independence >= 60 ? "you actively protect space for yourself, even inside close relationships" : "you don't tend to need much distance to feel like yourself"}.`
      : `Your responses suggest a particular relationship to personal space and autonomy worth reflecting on.`,
    your_vulnerability: context.dimensionScores.vulnerability !== undefined
      ? `Your vulnerability score (${Math.round(context.dimensionScores.vulnerability)}/100) suggests ${context.dimensionScores.vulnerability >= 60 ? "you tend to let people see the real, unedited version of you fairly readily" : "you tend to protect your inner world until safety feels well-established"}.`
      : `Your responses suggest a particular pattern in how openly you share what's underneath the surface.`,
    trust_and_security: `Your responses suggest trust and security aren't quite the same thing for you — one may come more easily than the other, and noticing which is which can be useful.`,
    distance_response: context.dimensionScores.distance_response !== undefined
      ? `When someone becomes less available, your responses (distance response: ${Math.round(context.dimensionScores.distance_response)}/100) suggest a fairly specific reaction pattern — worth noticing the next time it happens.`
      : `Your responses suggest a specific pattern in how you react when someone you're close to pulls back.`,
    communication_in_connection: `Your responses suggest a particular way you tend to voice — or not voice — what you need once you're close to someone.`,
    strengths:
      strengths.length > 0
        ? `Your responses suggest real strength in ${strengths.map((s) => s.toLowerCase()).join(", ")}.`
        : `Your responses suggest a measured, balanced approach rather than one standout trait.`,
    friction_points:
      friction.length > 0
        ? `One pattern worth noticing: ${friction.map((f) => f.toLowerCase()).join(", ")} scored lower — your responses suggest this could occasionally create friction, though it isn't a fixed trait.`
        : `Nothing in your responses stood out as a significant area of friction relative to your other patterns.`,
    inner_tension: topTension
      ? `Your responses suggest a real tension worth sitting with: ${topTension.label}. This isn't a contradiction — it's two genuine tendencies that can both be true for you at once.${topContradiction ? ` Your answers also didn't always point the same way on ${topContradiction.label.toLowerCase()} — that's less a fixed trait than a sign of how much it may depend on the situation.` : ""}`
      : topContradiction
        ? `Your responses didn't always point the same way on ${topContradiction.label.toLowerCase()} — rather than a fixed trait, this often means it depends on the situation: who you're with, how safe it feels, or what's at stake in the moment.`
        : `Your responses didn't reveal a strong tension between dimensions — your patterns appear to point in a fairly consistent direction.`,
    misunderstood_aspects: `People close to you may perceive the ${topLabel.toLowerCase()} in how you show up, even in moments when you don't feel it as strongly yourself.`,
    reflection: `A few questions worth sitting with: When did ${topLabel.toLowerCase()} last show up for you? What would it look like to lean on it slightly less, or slightly more, on purpose?`,
    final_note: `Your responses suggest ${context.primaryProfileName.toLowerCase()} is a real, current pattern — not a permanent label. Patterns like this can shift with attention and different circumstances.`,
    // Legacy keys kept for assessments still on the shorter 10-section structure.
    perception: `People close to you may perceive the ${topLabel.toLowerCase()} in how you show up, even in moments when you don't feel it as strongly yourself.`,
    what_you_need: bottom
      ? `One pattern in your answers is that ${humanize(bottom[0], context.dimensionLabels).toLowerCase()} scored lower (${Math.round(bottom[1])}/100) relative to your other patterns — your responses suggest this may be an area worth more of your own attention.`
      : `Your responses suggest a fairly balanced profile across the dimensions this assessment measures.`,
    how_you_react: `Under pressure, your responses suggest you tend to lean on the patterns that scored highest — particularly ${topLabel.toLowerCase()} — more than on the ones that scored lower.`,
    conclusion: `Your responses suggest ${context.primaryProfileName.toLowerCase()} is a real, current pattern — not a permanent label. Patterns like this can shift with attention and different circumstances.`,
  };

  return context.sections.map((spec) => ({
    key: spec.key,
    title: spec.title,
    body: byKey[spec.key] ?? context.primaryProfileDescription,
    aiGenerated: false,
  }));
}
