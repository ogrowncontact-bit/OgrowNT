import { findHardBannedTerms } from "./guardrails/nonDiagnosticFilter";
import type { GeneratedReportSection } from "./reportAI";
import type { ReportDocument } from "./reportDocument";

export type ReportQualityIssueType =
  | "missing_section"
  | "empty_section"
  | "banned_term"
  | "absolute_claim"
  | "repetitive"
  | "not_personalized"
  | "language_mismatch";

export interface ReportQualityIssue {
  type: ReportQualityIssueType;
  sectionKey?: string;
  detail: string;
}

export interface ReportQualityCheck {
  ok: boolean;
  issues: ReportQualityIssue[];
  wordCount: number;
}

const ABSOLUTE_CLAIM_PATTERNS: RegExp[] = [
  /\balways\b/i,
  /\bnever\b/i,
  /\bevery time\b/i,
  /\bwithout exception\b/i,
  /\bdefinitely will\b/i,
  /\bwill always\b/i,
  /\bwill never\b/i,
  /\bguaranteed\b/i,
  /\bcertain(ly)? (means|is|are)\b/i,
];

// Crude, deliberately cheap function-word check — not a language detector,
// just enough signal to catch "the AI ignored the language instruction and
// wrote English" (the failure mode this actually needs to guard against).
const LANGUAGE_MARKERS: Record<string, RegExp> = {
  en: /\b(the|and|you|your|suggest)\b/i,
  es: /\b(tu|tus|sugieren|que|para|con)\b/i,
  pt: /\b(seu|sua|sugerem|que|para|com)\b/i,
};

/**
 * Shared with the free-tier callers (profileAI.ts's generateFreeInsight,
 * profileEnrichmentAI.ts's per-insight filter) so a single short AI sentence
 * gets the same "no unsupported absolute claim" check the premium report's
 * per-section validateReportQuality already runs — without pulling in the
 * rest of that function's multi-section-shaped checks (repetition,
 * personalization-by-dimension-count), which don't apply to one sentence.
 */
export function containsAbsoluteClaim(text: string): boolean {
  return ABSOLUTE_CLAIM_PATTERNS.some((pattern) => pattern.test(text));
}

function normalizeForComparison(text: string): string {
  return text.toLowerCase().replace(/[^\w\s]/g, "").replace(/\s+/g, " ").trim();
}

/** Cheap overlap heuristic — not exact-duplicate detection, catches near-identical filler paragraphs across sections. */
function overlapRatio(a: string, b: string): number {
  const wordsA = new Set(normalizeForComparison(a).split(" "));
  const wordsB = new Set(normalizeForComparison(b).split(" "));
  if (wordsA.size === 0 || wordsB.size === 0) return 0;
  let shared = 0;
  for (const w of wordsA) if (wordsB.has(w)) shared += 1;
  return shared / Math.min(wordsA.size, wordsB.size);
}

export interface ValidateReportParams {
  sections: GeneratedReportSection[];
  expectedSectionKeys: string[];
  dimensionLabels: string[];
  primaryProfileName: string;
  language: string;
}

/**
 * Second, independent quality gate after generation — per-section
 * non-diagnostic filtering already runs inside generateReport(), this
 * checks the *assembled* report: structural completeness, no absolute
 * claims that slipped through, no near-duplicate sections, and a
 * personalization heuristic (does the report actually reference this
 * person's specific dimensions, or could it have been written for anyone
 * with this profile name). See docs/ARCHITECTURE.md §7.
 */
export function validateReportQuality(params: ValidateReportParams): ReportQualityCheck {
  const issues: ReportQualityIssue[] = [];
  const byKey = new Map(params.sections.map((s) => [s.key, s]));

  for (const key of params.expectedSectionKeys) {
    const section = byKey.get(key);
    if (!section) {
      issues.push({ type: "missing_section", sectionKey: key, detail: `Section "${key}" was not produced.` });
      continue;
    }
    if (!section.body.trim()) {
      issues.push({ type: "empty_section", sectionKey: key, detail: `Section "${key}" is empty.` });
      continue;
    }

    const banned = findHardBannedTerms(section.body);
    if (banned.length > 0) {
      issues.push({ type: "banned_term", sectionKey: key, detail: `Section "${key}" contains: ${banned.join(", ")}` });
    }

    for (const pattern of ABSOLUTE_CLAIM_PATTERNS) {
      if (pattern.test(section.body)) {
        issues.push({ type: "absolute_claim", sectionKey: key, detail: `Section "${key}" contains an absolute claim ("${pattern.source}").` });
        break;
      }
    }
  }

  // Repetition: any two sections sharing >70% of their (short) vocabulary read as the same paragraph reworded.
  for (let i = 0; i < params.sections.length; i++) {
    for (let j = i + 1; j < params.sections.length; j++) {
      if (overlapRatio(params.sections[i].body, params.sections[j].body) > 0.7) {
        issues.push({
          type: "repetitive",
          sectionKey: params.sections[j].key,
          detail: `Section "${params.sections[j].key}" reads as near-identical to "${params.sections[i].key}".`,
        });
      }
    }
  }

  // Personalization: the report should reference this person's actual profile name and at least a couple
  // of the dimensions this assessment measures — a purely generic report wouldn't need to.
  const allText = params.sections.map((s) => s.body).join(" ").toLowerCase();
  const mentionedDimensions = params.dimensionLabels.filter((label) => allText.includes(label.toLowerCase()));
  if (params.dimensionLabels.length > 0 && mentionedDimensions.length < Math.min(2, params.dimensionLabels.length)) {
    issues.push({
      type: "not_personalized",
      detail: `Report mentions only ${mentionedDimensions.length} of ${params.dimensionLabels.length} scored dimensions by name — reads as generic.`,
    });
  }

  const marker = LANGUAGE_MARKERS[params.language];
  if (marker && !marker.test(allText)) {
    issues.push({ type: "language_mismatch", detail: `Report doesn't appear to be written in the requested language ("${params.language}").` });
  }

  const wordCount = allText.split(/\s+/).filter(Boolean).length;

  // Hard-fail types only — repetition/absolute-claim/not_personalized/language_mismatch are recorded for
  // visibility (and per-section swap, see reportAI.ts) but don't alone block an otherwise-complete report;
  // missing/empty/banned always do.
  const hardFailTypes: ReportQualityIssueType[] = ["missing_section", "empty_section", "banned_term"];
  const ok = !issues.some((i) => hardFailTypes.includes(i.type));

  return { ok, issues, wordCount };
}

export type ReportDocumentQualityIssueType =
  | "missing_profile"
  | "missing_summary"
  | "missing_sections"
  | "placeholder_text"
  | "pdf_missing"
  | "pdf_invalid"
  | "recommendation_missing";

export interface ReportDocumentQualityIssue {
  type: ReportDocumentQualityIssueType;
  detail: string;
}

export interface ReportDocumentQualityCheck {
  /** False only for hard-fail issues (missing_profile/summary/sections, placeholder text, an unopenable PDF) — a missing recommendation is recorded but never blocks delivery, since not every profile has an eligible next assessment. */
  ok: boolean;
  issues: ReportDocumentQualityIssue[];
}

const PLACEHOLDER_PATTERNS: RegExp[] = [/\blorem ipsum\b/i, /\btodo\b/i, /\btbd\b/i, /\bplaceholder\b/i, /\{\{.*?\}\}/, /\[insert[^\]]*\]/i];

const HARD_FAIL_DOCUMENT_TYPES: ReportDocumentQualityIssueType[] = [
  "missing_profile",
  "missing_summary",
  "missing_sections",
  "placeholder_text",
  "pdf_missing",
  "pdf_invalid",
];

/**
 * Final gate before a Report is marked "ready" — the §QUALITY CONTROL
 * checklist run once against the fully-assembled ReportDocument (and,
 * where given, the rendered PDF bytes), on top of the per-section checks
 * `validateReportQuality` already ran during generation. "Page count valid"
 * and "links work" from the spec's checklist aren't implemented here: doing
 * either honestly needs a real PDF-parsing/crawling dependency this repo
 * doesn't carry, so they're a known, stated scope limit rather than a fake
 * pass — the magic-byte + minimum-size check below is a genuine, if
 * partial, substitute for "PDF generated, PDF opens".
 */
export function validateReportDocument(doc: ReportDocument, pdf?: Buffer): ReportDocumentQualityCheck {
  const issues: ReportDocumentQualityIssue[] = [];

  if (!doc.profile.name.trim() || !doc.profile.description.trim()) {
    issues.push({ type: "missing_profile", detail: "profile.name or profile.description is empty." });
  }
  if (!doc.summary.trim()) {
    issues.push({ type: "missing_summary", detail: "summary is empty." });
  }
  if (doc.sections.length === 0) {
    issues.push({ type: "missing_sections", detail: "No sections were produced." });
  }

  const allText = [doc.summary, ...doc.sections.map((s) => s.body), ...doc.reflectionQuestions].join(" ");
  for (const pattern of PLACEHOLDER_PATTERNS) {
    if (pattern.test(allText)) {
      issues.push({ type: "placeholder_text", detail: `Report contains placeholder-like text matching ${pattern.source}.` });
      break;
    }
  }

  if (pdf !== undefined) {
    if (pdf.length === 0) {
      issues.push({ type: "pdf_missing", detail: "PDF buffer is empty." });
    } else if (pdf.subarray(0, 5).toString("latin1") !== "%PDF-" || pdf.length < 1000) {
      issues.push({ type: "pdf_invalid", detail: "PDF buffer doesn't start with the %PDF- magic bytes, or is implausibly small." });
    }
  }

  if (!doc.recommendation) {
    issues.push({ type: "recommendation_missing", detail: "No next-discovery recommendation was available for this profile." });
  }

  const ok = !issues.some((i) => HARD_FAIL_DOCUMENT_TYPES.includes(i.type));
  return { ok, issues };
}
