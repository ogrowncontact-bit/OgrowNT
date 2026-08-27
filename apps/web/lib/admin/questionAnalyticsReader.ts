import { prisma } from "@inner/db";
import { VERSION_INCLUDE } from "../catalogMapper";

export interface RealQuestionAnalyticsRow {
  key: string;
  prompt: string;
  views: number;
  answers: number;
  /** (views - answers) / views — a question that was shown but not answered, distinct from never being reached at all. Null when never viewed. */
  skipRatePct: number | null;
  avgResponseTimeMs: number | null;
}

export interface RealQuestionAnalyticsResult {
  assessmentId: string;
  totalStarted: number;
  questions: RealQuestionAnalyticsRow[];
}

/**
 * FASE 33 §QUESTION ANALYTICS — real-traffic per-question stats (views,
 * answers, skip rate, average response time), distinct from FASE 31's
 * simulated 100-persona QA dashboard. Views come from the question_viewed
 * event (properties.questionKey only — never an answer); answers and
 * response time come from runtime.Response, which is never queried for its
 * answer content here (only questionId + responseTimeMs). Back-navigation
 * and per-question device/language are not tracked at this granularity —
 * see the FASE 33 deliverable for what that would require. Excludes FASE
 * 31's QA-simulation-tagged sessions — those write real Response rows
 * (skipAnalytics only suppresses their Event tracking) and would otherwise
 * silently understate the skip rate against real question_viewed counts,
 * which QA never fires at all.
 */
export async function getRealQuestionAnalytics(assessmentId: string): Promise<RealQuestionAnalyticsResult | null> {
  const version = await prisma.assessmentVersion.findFirst({
    where: { assessmentId, publishedAt: { not: null } },
    orderBy: { versionNumber: "desc" },
    include: VERSION_INCLUDE,
  });
  if (!version) return null;

  const notQaSimulation = { assessmentId, anonymousSession: { utmSource: { not: "qa_simulation" } } };

  const [totalStarted, viewEvents, responseStats] = await Promise.all([
    prisma.assessmentSession.count({ where: notQaSimulation }),
    prisma.event.findMany({
      where: { assessmentId, eventName: "question_viewed" },
      select: { properties: true },
    }),
    prisma.response.groupBy({
      by: ["questionId"],
      where: { assessmentSession: notQaSimulation },
      _count: { _all: true },
      _avg: { responseTimeMs: true },
    }),
  ]);

  const viewCountByKey = new Map<string, number>();
  for (const event of viewEvents) {
    const key = (event.properties as { questionKey?: string } | null)?.questionKey;
    if (!key) continue;
    viewCountByKey.set(key, (viewCountByKey.get(key) ?? 0) + 1);
  }

  const answerStatsByKey = new Map(responseStats.map((r) => [r.questionId, r]));

  const questions: RealQuestionAnalyticsRow[] = version.questions
    .filter((q) => q.isCore)
    .map((q) => {
      const views = viewCountByKey.get(q.key) ?? 0;
      const answerStat = answerStatsByKey.get(q.key);
      const answers = answerStat?._count._all ?? 0;
      return {
        key: q.key,
        prompt: q.prompt,
        views,
        answers,
        // question_viewed is a best-effort client beacon (can be missed on a
        // flaky connection even though the answer still submits), so clamp
        // at 0 rather than surface a misleading negative "skip rate."
        skipRatePct: views > 0 ? Math.max(0, Math.round(((views - answers) / views) * 1000) / 10) : null,
        avgResponseTimeMs: answerStat?._avg.responseTimeMs ? Math.round(answerStat._avg.responseTimeMs) : null,
      };
    });

  return { assessmentId, totalStarted, questions };
}
