import type { DimensionDirection } from "@/lib/demoPersonas";

export interface QaPersona {
  key: string;
  label: string;
  targetDirections: Partial<Record<string, DimensionDirection>>;
}

// LOVE's own 10 scored dimensions (packages/content/src/assessments/love.ts).
// The spec's example extreme cases reference "boundaries" and "reassurance",
// which aren't LOVE-scored dimension keys — mapped to LOVE's closest real
// ones (independence for boundaries-style self-protection, validation for
// reassurance-seeking) rather than inventing dimensions the engine doesn't
// actually compute.
const LOVE_DIMENSIONS = [
  "connection",
  "independence",
  "trust",
  "vulnerability",
  "emotional_openness",
  "validation",
  "security",
  "conflict",
  "affection_expression",
  "distance_response",
];

// Deterministic PRNG (mulberry32) — the same 100 personas every run, so a
// re-run of the QA simulation is comparable to the last one rather than
// noise from a different random sample each time.
function mulberry32(seed: number) {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const EXTREME_CASES: QaPersona[] = [
  { key: "extreme_conn_high_indep_high", label: "Very high connection + very high independence", targetDirections: { connection: "high", independence: "high" } },
  { key: "extreme_conn_low_indep_low", label: "Very low connection + very low independence", targetDirections: { connection: "low", independence: "low" } },
  { key: "extreme_trust_high_vuln_low", label: "High trust + low vulnerability", targetDirections: { trust: "high", vulnerability: "low" } },
  { key: "extreme_trust_low_vuln_high", label: "Low trust + high vulnerability", targetDirections: { trust: "low", vulnerability: "high" } },
  { key: "extreme_validation_high_indep_high", label: "High reassurance-seeking (validation) + high independence", targetDirections: { validation: "high", independence: "high" } },
  { key: "extreme_vuln_high_openness_low", label: "High vulnerability + low emotional expression", targetDirections: { vulnerability: "high", emotional_openness: "low" } },
  { key: "extreme_conn_high_indep_boundaries", label: "High connection + strong self-protection (independence)", targetDirections: { connection: "high", independence: "high", vulnerability: "low" } },
  { key: "extreme_openness_high_indep_high", label: "High emotional openness + high independence", targetDirections: { emotional_openness: "high", independence: "high" } },
  { key: "extreme_indep_high_distance_low", label: "High independence + low tolerance for distance", targetDirections: { independence: "high", distance_response: "low" } },
  { key: "extreme_trust_low_security_low", label: "Low trust + low security", targetDirections: { trust: "low", security: "low" } },
  { key: "extreme_conflict_high_affection_low", label: "High conflict engagement + low affection expression", targetDirections: { conflict: "high", affection_expression: "low" } },
  { key: "extreme_validation_high_security_low", label: "High reassurance-seeking + low security", targetDirections: { validation: "high", security: "low" } },
  { key: "extreme_conn_high_vuln_high_trust_high", label: "High connection + high vulnerability + high trust", targetDirections: { connection: "high", vulnerability: "high", trust: "high" } },
  { key: "extreme_indep_high_vuln_low_distance_high", label: "High independence + low vulnerability + high distance tolerance", targetDirections: { independence: "high", vulnerability: "low", distance_response: "high" } },
  { key: "extreme_conflict_low_conn_high_validation_high", label: "Conflict-avoidant + high connection + high reassurance-seeking", targetDirections: { conflict: "low", connection: "high", validation: "high" } },
];

/**
 * FASE 31 §SIMULATION PERSONAS/§EXTREME CASES — 100 deterministic, varied
 * LOVE personas: one solo high/low per dimension (20), the spec's named
 * extreme/contradictory combinations adapted to LOVE's real dimension set
 * (15), several "balanced" runs with no target at all (5, to check the
 * neutral tie-break's own consistency), and the remainder filled by a
 * seeded random walk over 2-4 dimensions each. Reused by
 * lib/qa/runLoveQaSimulation.ts to drive the real engine via
 * lib/demoAnswerSelection.ts's chooseAnswerForPersona — never a fabricated
 * report, always a real answered session.
 */
export function generateLoveQaPersonas(count = 100): QaPersona[] {
  const personas: QaPersona[] = [];
  const seen = new Set<string>();

  function add(persona: QaPersona) {
    const signature = JSON.stringify(Object.entries(persona.targetDirections).sort());
    if (seen.has(signature)) return false;
    seen.add(signature);
    personas.push(persona);
    return true;
  }

  for (const dim of LOVE_DIMENSIONS) {
    add({ key: `solo_${dim}_high`, label: `High ${dim}`, targetDirections: { [dim]: "high" } });
    add({ key: `solo_${dim}_low`, label: `Low ${dim}`, targetDirections: { [dim]: "low" } });
  }

  for (const c of EXTREME_CASES) add(c);

  for (let i = 0; i < 5; i++) {
    add({ key: `balanced_${i}`, label: `Balanced (replicate ${i + 1})`, targetDirections: {} });
  }

  const rand = mulberry32(42);
  let guard = 0;
  while (personas.length < count && guard < count * 20) {
    guard++;
    const dimCount = 2 + Math.floor(rand() * 3); // 2-4 dimensions
    const shuffled = [...LOVE_DIMENSIONS].sort(() => rand() - 0.5);
    const chosen = shuffled.slice(0, dimCount);
    const targetDirections: Partial<Record<string, DimensionDirection>> = {};
    for (const dim of chosen) targetDirections[dim] = rand() < 0.5 ? "high" : "low";
    add({ key: `random_${personas.length}_${guard}`, label: `Mixed pattern (${chosen.join(", ")})`, targetDirections });
  }

  return personas.slice(0, count);
}
