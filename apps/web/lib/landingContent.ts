import type { AssessmentConfig } from "@inner/assessment-engine";
import { prisma } from "@inner/db";
import { sectionObjectiveFor, type SectionRole } from "@inner/ai";

/**
 * Landing-page copy derived entirely from real config data — no fabricated
 * social proof, stats, or testimonials (the spec's own explicit
 * instruction: "If there is no real data, hide these sections"). FAQ
 * answers describe actual implemented behavior only.
 */

export interface FaqItem {
  question: string;
  answer: string;
}

/**
 * CMS-editable landing copy, admin-editable via the "Landing Page" section
 * of AssessmentEditor.tsx without touching code (FASE 23 §CONTENT MODEL).
 * Lives on Assessment directly (see schema.prisma), separate from
 * AssessmentConfig — this is presentation copy, not scoring config, and
 * keeping it out of the assessment-engine's framework-free domain type
 * avoids mixing concerns that don't belong together.
 */
export interface LandingContentOverrides {
  headline: string | null;
  subheadline: string | null;
  curiosityHook: string | null;
  exampleInsight: string | null;
  ctaLabel: string | null;
  extraFaqItems: FaqItem[];
}

export async function getLandingContentOverrides(slug: string): Promise<LandingContentOverrides> {
  const row = await prisma.assessment.findUnique({
    where: { slug },
    select: { landingHeadline: true, landingSubheadline: true, curiosityHook: true, exampleInsight: true, ctaLabel: true, extraFaqItems: true },
  });
  return {
    headline: row?.landingHeadline ?? null,
    subheadline: row?.landingSubheadline ?? null,
    curiosityHook: row?.curiosityHook ?? null,
    exampleInsight: row?.exampleInsight ?? null,
    ctaLabel: row?.ctaLabel ?? null,
    extraFaqItems: (row?.extraFaqItems as FaqItem[] | null) ?? [],
  };
}

export function getFaqItems(config: AssessmentConfig, extraFaqItems: FaqItem[] = []): FaqItem[] {
  const nameEndsWithPunctuation = /[?!.]$/.test(config.name);
  const base: FaqItem[] = [
    {
      question: nameEndsWithPunctuation ? `What is "${config.name}"` : `What is "${config.name}"?`,
      answer: config.description,
    },
    {
      question: "How long does it take?",
      answer: `About ${config.recommendedQuestions} questions — most people finish in 4 to 7 minutes.`,
    },
    {
      question: "Is this a psychological diagnosis?",
      answer:
        "No. INNER isn't a diagnostic or clinical tool. It reflects patterns in how you answered a specific set of questions, not a medical or psychological assessment.",
    },
    {
      question: "Do I need an account?",
      answer: "No. You can start right away — no sign-up, no password. We only ask for an email if you choose to unlock your full report.",
    },
    {
      question: "What happens after I finish?",
      answer: "You'll see a free result immediately, with the option to unlock a deeper, personalized report if you'd like to go further.",
    },
    {
      question: "How do I receive my report?",
      answer: "It's available right away on the page, and we also email you a PDF copy along with a link back to it.",
    },
    {
      question: "Can I access my report later?",
      answer: "Yes. Use the same email you purchased with to request a secure access link anytime from the site's access page.",
    },
    {
      question: "Is this therapy?",
      answer:
        "No. INNER doesn't replace therapy or professional support. It's a self-reflection tool — if you're working through something serious, a licensed professional is the right place for that.",
    },
  ];
  return [...base, ...extraFaqItems];
}

/** Shared trust copy — identical on every /[slug] landing page and the homepage. */
export const TRUST_POINTS = [
  "No account required to start",
  "Your email is only used to deliver your report and, only with your consent, occasional relevant updates",
  "Your responses are private — never sold or publicly exposed",
  "Access your reports anytime through a secure link sent to your email",
];

export interface DiscoveryPoint {
  title: string;
}

/**
 * A curated subset of the premium report's own section titles — genuine
 * content the report actually contains, not invented teaser copy. Picks
 * up to 5, skipping the more generic wrap-up sections (signature/strengths/
 * friction/tension/reflection/final note) in favor of ones specific to
 * this particular assessment's subject matter.
 */
const GENERIC_SECTION_KEYS = new Set([
  "signature",
  "dominant_pattern",
  "strengths",
  "friction_points",
  "blind_spots",
  "inner_tension",
  "reflection",
  "final_note",
  "misunderstood_aspects",
]);

export function getDiscoveryPoints(config: AssessmentConfig): DiscoveryPoint[] {
  const specific = config.premiumReportStructure.filter((s) => !GENERIC_SECTION_KEYS.has(s.key));
  const pool = specific.length >= 3 ? specific : config.premiumReportStructure;
  return pool.slice(0, 5).map((s) => ({ title: s.title }));
}

/**
 * "What's inside the premium report" (FASE 23 §PREMIUM REPORT SECTION) —
 * derived from the same SectionRole taxonomy the report engine itself uses
 * to tag every generated section (packages/ai/src/promptEngine/
 * sectionObjectives.ts), plus the two fields every ReportDocument always
 * carries (reflectionQuestions, recommendation). Real structure, not
 * invented marketing copy — never states a page count, since none is
 * configured anywhere in the system.
 */
const ROLE_LABELS: Record<SectionRole, string> = {
  signature: "Your signature pattern",
  core_pattern: "Core patterns",
  strengths: "Strengths",
  friction: "Where things can get complicated",
  tension: "Hidden tensions",
  how_you_come_across: "How you may come across",
  under_pressure: "How you respond under pressure",
  reflection: "Reflection questions",
  closing: "Closing thoughts",
  narrative: "Personalized interpretation",
};

export function getPremiumPreviewItems(config: AssessmentConfig): string[] {
  const roles = new Set<SectionRole>();
  for (const section of config.premiumReportStructure) {
    roles.add(sectionObjectiveFor(section.key, section.title).role);
  }
  const items = [...roles].map((r) => ROLE_LABELS[r]);
  if (!items.includes(ROLE_LABELS.reflection)) items.push(ROLE_LABELS.reflection);
  items.push("Your next discovery");
  return [...new Set(items)];
}
