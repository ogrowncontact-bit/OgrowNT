import type { Question } from "@inner/assessment-engine";

/** Strips scoring internals (dimension contributions) before a question ever reaches the client. */
export interface ClientQuestion {
  key: string;
  type: Question["type"];
  prompt: string;
  options?: { key: string; label: string }[];
  scaleMax?: number;
}

export function toClientQuestion(q: Question): ClientQuestion {
  return {
    key: q.key,
    type: q.type,
    prompt: q.prompt,
    options: q.options?.map((o) => ({ key: o.key, label: o.label })),
    scaleMax: q.scaleMax,
  };
}
