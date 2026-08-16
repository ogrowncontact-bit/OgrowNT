import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { getAssessmentConfig } from "@/lib/assessments";
import { ensureAnonymousSession } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

/**
 * The anonymous session is created here — on first landing view, not on
 * "Begin" — so acquisition (UTM, referrer) is captured even for visitors
 * who never start the assessment. Route Handlers (unlike Server Component
 * renders) are allowed to set cookies, which is why this isn't inlined
 * into the landing page itself.
 */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const slug = body?.slug as string | undefined;
  if (!slug) return NextResponse.json({ error: "slug is required" }, { status: 400 });

  const [config, assessment] = await Promise.all([
    getAssessmentConfig(slug),
    prisma.assessment.findUnique({ where: { slug }, select: { id: true } }),
  ]);
  if (!config || !assessment) return NextResponse.json({ error: "Unknown assessment" }, { status: 404 });

  const utm = {
    utmSource: body?.utm?.utm_source,
    utmMedium: body?.utm?.utm_medium,
    utmCampaign: body?.utm?.utm_campaign,
    utmContent: body?.utm?.utm_content,
    utmTerm: body?.utm?.utm_term,
  };

  const anonymousSessionId = await ensureAnonymousSession({ firstLandingSlug: slug, utm });
  await track({ anonymousSessionId, eventName: "landing_view", assessmentId: assessment.id, properties: { slug }, utm });

  return NextResponse.json({ ok: true });
}
