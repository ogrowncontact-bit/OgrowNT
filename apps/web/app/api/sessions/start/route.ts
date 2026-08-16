import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { getAssessmentConfig } from "@/lib/assessments";
import { ensureAnonymousSession } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const slug = body?.slug as string | undefined;
  if (!slug) return NextResponse.json({ error: "slug is required" }, { status: 400 });

  const config = await getAssessmentConfig(slug);
  if (!config) return NextResponse.json({ error: `Unknown assessment "${slug}"` }, { status: 404 });

  const utm = {
    utmSource: body?.utm?.utm_source,
    utmMedium: body?.utm?.utm_medium,
    utmCampaign: body?.utm?.utm_campaign,
    utmContent: body?.utm?.utm_content,
    utmTerm: body?.utm?.utm_term,
  };

  const anonymousSessionId = await ensureAnonymousSession({ firstLandingSlug: slug, utm });

  const assessment = await prisma.assessment.findUnique({ where: { slug } });
  if (!assessment) {
    return NextResponse.json({ error: `Assessment "${slug}" is not seeded in the catalog yet.` }, { status: 500 });
  }
  const version = await prisma.assessmentVersion.findFirst({
    where: { assessmentId: assessment.id, publishedAt: { not: null } },
    orderBy: { versionNumber: "desc" },
  });
  if (!version) {
    return NextResponse.json({ error: `Assessment "${slug}" has no published version.` }, { status: 500 });
  }

  const session = await prisma.assessmentSession.create({
    data: {
      anonymousSessionId,
      assessmentId: assessment.id,
      assessmentVersionId: version.id,
      sourceSlug: slug,
    },
  });

  await track({
    anonymousSessionId,
    eventName: "assessment_started",
    assessmentId: assessment.id,
    utm,
  });

  return NextResponse.json({ assessmentSessionId: session.id });
}
