import { prisma } from "@inner/db";
import { startSession, submitAnswer, type AssessmentConfig, type SessionState } from "@inner/assessment-engine";
import { decryptText } from "./security/encryption";

interface StoredAnswer {
  questionKey: string;
  selectedOptionKeys?: string[];
  scaleValue?: number;
  openText?: string;
  answeredAt: Date;
}

/**
 * Rebuilds the deterministic SessionState by replaying persisted answers
 * back through the same engine that produced them — no separate "current
 * state" blob to fall out of sync. Fine at this volume/question-count; if
 * this ever becomes a hot path, cache the folded state instead of the raw
 * rows.
 */
export async function reconstructSessionState(
  config: AssessmentConfig,
  assessmentSessionId: string
): Promise<SessionState> {
  const [responses, openResponses] = await Promise.all([
    prisma.response.findMany({ where: { assessmentSessionId }, orderBy: { answeredAt: "asc" } }),
    prisma.openResponse.findMany({ where: { assessmentSessionId }, orderBy: { createdAt: "asc" } }),
  ]);

  const answers: StoredAnswer[] = [
    ...responses.map((r) => ({
      questionKey: r.questionId,
      selectedOptionKeys: (r.selectedOptionIds as string[] | null) ?? undefined,
      scaleValue: r.scaleValue ?? undefined,
      answeredAt: r.answeredAt,
    })),
    ...openResponses.map((r) => ({
      questionKey: r.questionId,
      openText: decryptText(r.rawTextEncrypted),
      answeredAt: r.createdAt,
    })),
  ].sort((a, b) => a.answeredAt.getTime() - b.answeredAt.getTime());

  let state = startSession(config);
  for (const answer of answers) {
    const result = submitAnswer(config, state, answer);
    state = result.state;
  }
  return state;
}
