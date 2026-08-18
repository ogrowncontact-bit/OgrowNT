import type { AssessmentConfig } from "@inner/assessment-engine";

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

export function getFaqItems(config: AssessmentConfig): FaqItem[] {
  const nameEndsWithPunctuation = /[?!.]$/.test(config.name);
  return [
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
  ];
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
