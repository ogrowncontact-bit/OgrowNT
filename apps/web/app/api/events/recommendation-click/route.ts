import { NextRequest, NextResponse } from "next/server";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

/**
 * Fired client-side the moment someone clicks a recommendation CTA — the
 * one discovery-funnel step that previously had no event at all (see
 * lib/admin/dashboardReader.ts's "no recommendation_clicked event exists
 * yet" comment). Best-effort: a failed beacon must never block navigation.
 */
export async function POST(request: NextRequest) {
  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) return NextResponse.json({ ok: true }); // nothing to attribute this to — not an error

  const body = await request.json().catch(() => null);
  const fromAssessmentId = body?.fromAssessmentId as string | undefined;
  const toSlug = body?.toSlug as string | undefined;
  if (!fromAssessmentId || !toSlug) return NextResponse.json({ error: "fromAssessmentId and toSlug are required" }, { status: 400 });

  await track({
    anonymousSessionId,
    eventName: "recommendation_clicked",
    assessmentId: fromAssessmentId,
    properties: { toSlug },
  });

  return NextResponse.json({ ok: true });
}
