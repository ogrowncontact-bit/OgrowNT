import type { ToneConfig } from "./types";

function bucket(value: number): "low" | "medium" | "high" {
  if (value >= 0.66) return "high";
  if (value >= 0.33) return "medium";
  return "low";
}

const WARMTH_PHRASE = { low: "understated and matter-of-fact rather than emotionally warm", medium: "measured warmth", high: "genuinely warm, like someone who cares how this lands" };
const DIRECTNESS_PHRASE = { low: "gentle, softened phrasing — never blunt", medium: "clear but not blunt", high: "name the pattern plainly, without softening it into vagueness" };
const DEPTH_PHRASE = { low: "brief and concrete — one clear idea per sentence", medium: "a natural amount of elaboration", high: "willing to elaborate and connect ideas across dimensions, not just state them" };
const FORMALITY_PHRASE = { low: "conversational and natural — contractions are fine", medium: "a natural, adult register", high: "a slightly more composed, formal register" };

/** Turns 0..1 tone parameters into instruction phrasing — never sent to the model as raw numbers (§TONE CONFIGURATION). */
export function toneVoiceInstruction(tone: ToneConfig): string {
  return (
    `Voice calibration for this assessment: ${WARMTH_PHRASE[bucket(tone.warmth)]}; ${DIRECTNESS_PHRASE[bucket(tone.directness)]}; ` +
    `${DEPTH_PHRASE[bucket(tone.depth)]}; ${FORMALITY_PHRASE[bucket(tone.formality)]}.`
  );
}
