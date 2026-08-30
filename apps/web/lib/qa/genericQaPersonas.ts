import type { QaPersona } from "@/lib/qa/loveQaPersonas";

/**
 * §GENERIC QA PERSONAS — a dimension-agnostic version of
 * lib/qa/loveQaPersonas.ts, built so the 100-persona QA simulation (FASE 31,
 * originally LOVE-only) can drive any of the other assessments without a
 * hand-curated persona file per assessment.
 *
 * LOVE's own persona set includes 15 named "extreme case" combinations
 * (e.g. "high trust + low vulnerability") chosen by hand for LOVE's specific
 * relationship semantics — that curation doesn't transfer to a differently
 * themed assessment (e.g. `relationship`'s `expectations` or `communication`
 * dimensions don't map onto LOVE's hand-picked pairs at all). Rather than
 * inventing semantics we don't actually understand for each assessment, this
 * generator produces the same *shape* of coverage programmatically: solo
 * high/low per dimension (full single-dimension coverage, same as LOVE),
 * deterministic pairwise extreme combinations across the dimension set
 * (structural analogue of LOVE's named extremes, without asserting a
 * semantic story for each pair), balanced replicates, and a seeded random
 * fill — same reasoning as LOVE's generator: deterministic so re-runs are
 * comparable, not fresh noise each time.
 */
export function generateQaPersonas(dimensionKeys: string[], count = 100): QaPersona[] {
  const personas: QaPersona[] = [];
  const seen = new Set<string>();

  function add(persona: QaPersona) {
    const signature = JSON.stringify(Object.entries(persona.targetDirections).sort());
    if (seen.has(signature)) return false;
    seen.add(signature);
    personas.push(persona);
    return true;
  }

  // Deterministic PRNG (mulberry32) — same algorithm as loveQaPersonas.ts,
  // seeded the same way, so results are stable across runs and comparable
  // assessment-to-assessment.
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

  for (const dim of dimensionKeys) {
    add({ key: `solo_${dim}_high`, label: `High ${dim}`, targetDirections: { [dim]: "high" } });
    add({ key: `solo_${dim}_low`, label: `Low ${dim}`, targetDirections: { [dim]: "low" } });
  }

  // Deterministic pairwise extremes: every adjacent pair in the dimension
  // list (as authored in the assessment's config, so the pairing is stable
  // and reproducible) gets a high/high, low/low, and high/low persona. This
  // caps combinatorial growth at ~3x the dimension count rather than the
  // full pairwise product, matching roughly the same persona-count share
  // LOVE's 15 hand-picked extremes occupied out of its 10 dimensions.
  const pairRand = mulberry32(7);
  for (let i = 0; i < dimensionKeys.length; i++) {
    const a = dimensionKeys[i];
    const b = dimensionKeys[(i + 1) % dimensionKeys.length];
    if (a === b) continue;
    add({ key: `extreme_${a}_high_${b}_high`, label: `High ${a} + high ${b}`, targetDirections: { [a]: "high", [b]: "high" } });
    add({ key: `extreme_${a}_low_${b}_low`, label: `Low ${a} + low ${b}`, targetDirections: { [a]: "low", [b]: "low" } });
    const swap = pairRand() < 0.5;
    add({
      key: `extreme_${a}_${swap ? "high" : "low"}_${b}_${swap ? "low" : "high"}`,
      label: `${swap ? "High" : "Low"} ${a} + ${swap ? "low" : "high"} ${b}`,
      targetDirections: { [a]: swap ? "high" : "low", [b]: swap ? "low" : "high" },
    });
  }

  for (let i = 0; i < 5; i++) {
    add({ key: `balanced_${i}`, label: `Balanced (replicate ${i + 1})`, targetDirections: {} });
  }

  const rand = mulberry32(42);
  let guard = 0;
  while (personas.length < count && guard < count * 20) {
    guard++;
    const dimCount = Math.min(dimensionKeys.length, 2 + Math.floor(rand() * 3)); // 2-4 dimensions, capped by however many the assessment actually has
    const shuffled = [...dimensionKeys].sort(() => rand() - 0.5);
    const chosen = shuffled.slice(0, dimCount);
    const targetDirections: QaPersona["targetDirections"] = {};
    for (const dim of chosen) targetDirections[dim] = rand() < 0.5 ? "high" : "low";
    add({ key: `random_${personas.length}_${guard}`, label: `Mixed pattern (${chosen.join(", ")})`, targetDirections });
  }

  return personas.slice(0, count);
}
