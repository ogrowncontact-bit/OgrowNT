import { callStructured, isAiEnabled, MODELS } from "./client";
import { enforceNonDiagnostic } from "./guardrails/nonDiagnosticFilter";

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

interface GenerateReportParams {
  assessmentName: string;
  primaryProfileName: string;
  primaryProfileDescription: string;
  secondaryProfileNames: string[];
  dimensionScores: Record<string, number>; // key -> normalized 0-100
  dimensionLabels?: Record<string, string>;
  openAnswerTags: string[];
  sections: ReportSectionSpec[];
}

/**
 * Generates every premiumReportStructure section in one call (cheaper/
 * faster than one call per section) — each section's output is
 * independently checked against the non-diagnostic filter, and only the
 * sections that fail fall back to the deterministic template, so one bad
 * section never sinks the whole report. See docs/ARCHITECTURE.md §7.
 */
export async function generateReport(params: GenerateReportParams): Promise<{ sections: GeneratedReportSection[] }> {
  if (!isAiEnabled()) {
    return { sections: buildFallbackSections(params) };
  }

  const scoreLines = Object.entries(params.dimensionScores)
    .map(([dim, score]) => `${humanize(dim, params.dimensionLabels)}: ${Math.round(score)}/100`)
    .join(", ");

  const result = await callStructured<Record<string, string>>({
    model: MODELS.quality,
    system:
      "You write a premium, warm, specific personal-reflection report for a self-reflection app. The " +
      "person's dominant pattern has ALREADY been determined by a separate scoring system — you are " +
      "narrating and expanding on it section by section, never diagnosing anything new or contradicting " +
      "the given profile. Each section is 2-4 sentences, specific to their actual scores (reference " +
      "dimensions by name where natural), never generic filler. Use hedged language throughout: " +
      "'your responses suggest...', 'you appear to...', 'one pattern is...'. Never say 'you are' or " +
      "'you have' as a bare claim, and never use clinical/diagnostic terms (disorder, syndrome, diagnosis, " +
      "trauma, narcissistic, codependent, pathological, etc). Never claim certainty or that any trait is fixed.",
    userMessage:
      `Assessment: ${params.assessmentName}\n` +
      `Primary pattern: ${params.primaryProfileName} — ${params.primaryProfileDescription}\n` +
      `Secondary patterns: ${params.secondaryProfileNames.join(", ") || "(none)"}\n` +
      `Dimension scores: ${scoreLines}\n` +
      `Themes from their own words: ${params.openAnswerTags.join(", ") || "(none)"}\n\n` +
      `Write one section for each of:\n${params.sections.map((s) => `- ${s.key}: "${s.title}"`).join("\n")}`,
    toolName: "write_report",
    toolDescription: "Record the report, one body per section key.",
    inputSchema: {
      type: "object",
      properties: Object.fromEntries(params.sections.map((s) => [s.key, { type: "string", maxLength: 800 }])),
      required: params.sections.map((s) => s.key),
    },
    maxTokens: 2000,
  });

  const fallback = buildFallbackSections(params);
  if (!result.ok) return { sections: fallback };

  return {
    sections: params.sections.map((spec, i) => {
      const raw = result.data[spec.key];
      if (typeof raw !== "string" || !raw.trim()) return fallback[i];
      const filtered = enforceNonDiagnostic(raw.trim());
      if (!filtered.ok) return fallback[i]; // that section falls back; the rest of the report is unaffected
      return { key: spec.key, title: spec.title, body: filtered.text, aiGenerated: true };
    }),
  };
}

function humanize(key: string, labels?: Record<string, string>): string {
  return labels?.[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Deterministic, dimension-driven fallback — works for any assessment's
 * report structure without assessment-specific code, and is what every
 * report is built from when AI is unavailable (§7). Not as rich as a real
 * generation, but never empty and never generic-feeling: it's parameterized
 * by this session's actual scores.
 */
function buildFallbackSections(params: GenerateReportParams): GeneratedReportSection[] {
  const entries = Object.entries(params.dimensionScores);
  const sorted = [...entries].sort((a, b) => b[1] - a[1]);
  const top = sorted[0];
  const bottom = sorted[sorted.length - 1];
  const strengths = sorted.filter(([, score]) => score >= 65).slice(0, 3);
  const frictions = sorted.filter(([, score]) => score <= 35).slice(0, 3);
  const topLabel = top ? humanize(top[0], params.dimensionLabels) : "your dominant pattern";

  const byKey: Record<string, string> = {
    signature: `Your INNER Signature: ${params.primaryProfileName}. ${params.primaryProfileDescription}`,
    dominant_pattern: top
      ? `Your responses point most strongly toward ${topLabel} (${Math.round(top[1])}/100), which shapes much of how ${params.primaryProfileName.toLowerCase()} shows up for you day to day.`
      : params.primaryProfileDescription,
    how_you_connect: `Your responses suggest a connection style shaped by where ${topLabel.toLowerCase()} sits for you — this tends to influence how quickly you let people in and how you respond once they're close.`,
    what_you_need: bottom
      ? `One pattern in your answers is that ${humanize(bottom[0], params.dimensionLabels).toLowerCase()} scored lower (${Math.round(bottom[1])}/100) relative to your other patterns — your responses suggest this may be an area worth more of your own attention.`
      : `Your responses suggest a fairly balanced profile across the dimensions this assessment measures.`,
    how_you_react: `Under pressure, your responses suggest you tend to lean on the patterns that scored highest — particularly ${topLabel.toLowerCase()} — more than on the ones that scored lower.`,
    strengths:
      strengths.length > 0
        ? `Your responses suggest real strength in ${strengths.map(([k]) => humanize(k, params.dimensionLabels).toLowerCase()).join(", ")}.`
        : `Your responses suggest a measured, balanced approach rather than one standout trait.`,
    friction_points:
      frictions.length > 0
        ? `One pattern worth noticing: ${frictions.map(([k]) => humanize(k, params.dimensionLabels).toLowerCase()).join(", ")} scored lower — your responses suggest this could occasionally create friction, though it isn't a fixed trait.`
        : `Nothing in your responses stood out as a significant area of friction relative to your other patterns.`,
    perception: `People close to you may perceive the ${topLabel.toLowerCase()} in how you show up, even in moments when you don't feel it as strongly yourself.`,
    reflection: `A few questions worth sitting with: When did ${topLabel.toLowerCase()} last show up for you? What would it look like to lean on it slightly less, or slightly more, on purpose?`,
    conclusion: `Your responses suggest ${params.primaryProfileName.toLowerCase()} is a real, current pattern — not a permanent label. Patterns like this can shift with attention and different circumstances.`,
  };

  return params.sections.map((spec) => ({
    key: spec.key,
    title: spec.title,
    body: byKey[spec.key] ?? params.primaryProfileDescription,
    aiGenerated: false,
  }));
}
