import { NextRequest, NextResponse } from "next/server";
import { startSession, submitAnswer, nextQuestion, type AnswerInput, type SessionState } from "@inner/assessment-engine";
import { requireAdmin } from "@/lib/adminAuth";
import { loadAssessmentForEdit } from "@/lib/admin/catalogReader";
import { toClientQuestion } from "@/lib/clientQuestion";

/**
 * Lets an admin click through the adaptive engine's actual question
 * selection live, against the assessment's current draft (or latest
 * published version if there's no draft) — never a real AssessmentSession,
 * never persisted. State round-trips through the client on every step
 * instead of being kept server-side, since there's nothing here worth a DB
 * row. Surfaces dimensionScores (confidence/consistency) so an admin can SEE
 * why a question was picked — that's an admin diagnostic, not something the
 * real end-user assessment ever reveals.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  await requireAdmin();
  const { id } = await params;

  const loaded = await loadAssessmentForEdit(id);
  if (!loaded) return NextResponse.json({ error: "Assessment not found" }, { status: 404 });
  const { config } = loaded;

  const body = await request.json().catch(() => null);
  const incomingState = body?.state as SessionState | undefined;
  const answer = body?.answer as AnswerInput | undefined;

  let state: SessionState;
  if (!incomingState) {
    state = startSession(config);
  } else if (answer) {
    const result = submitAnswer(config, incomingState, answer);
    state = result.state;
  } else {
    state = incomingState;
  }

  const question = nextQuestion(config, state);

  return NextResponse.json({
    state,
    question: question ? toClientQuestion(question) : null,
    isComplete: state.status === "completed",
    progress: { asked: state.askedQuestionKeys.length, recommended: config.recommendedQuestions, max: config.maxQuestions },
  });
}
