import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";

function isValidBootstrapSecret(provided: string | null, cronSecret: string | undefined): boolean {
  if (!cronSecret || !provided) return false;
  const expected = Buffer.from(cronSecret);
  const actual = Buffer.from(provided);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

/**
 * One-time bootstrap for the first LOVE paid-traffic test round: creates the
 * four Meta Ads campaigns (dor/curiosidade x texto/screenshot) the admin
 * asked for, each with its own UTM campaignParam so /admin/launch/love can
 * break results out per creative. Same GET+CRON_SECRET shape as
 * bootstrap-seed (see that route) since this is a one-off fetch, not a
 * scheduler. Idempotent per campaignParam: skips any that already exist, so
 * hitting this twice is harmless.
 */
const CAMPAIGNS = [
  { param: "dor-texto", creative: "Dor — Texto", name: "LOVE — Dor — Texto (Meta)" },
  { param: "dor-screenshot", creative: "Dor — Screenshot", name: "LOVE — Dor — Screenshot (Meta)" },
  { param: "curiosidade-texto", creative: "Curiosidade — Texto", name: "LOVE — Curiosidade — Texto (Meta)" },
  { param: "curiosidade-screenshot", creative: "Curiosidade — Screenshot", name: "LOVE — Curiosidade — Screenshot (Meta)" },
] as const;

export async function GET(request: NextRequest) {
  const providedSecret = request.nextUrl.searchParams.get("secret");
  if (!isValidBootstrapSecret(providedSecret, process.env.CRON_SECRET)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: process.env.CRON_SECRET ? 401 : 503 });
  }

  const love = await prisma.assessment.findUnique({ where: { slug: "love" }, select: { id: true } });
  if (!love) {
    return NextResponse.json({ error: "LOVE assessment not found — seed the catalog first" }, { status: 409 });
  }

  const created: string[] = [];
  const skipped: string[] = [];
  for (const c of CAMPAIGNS) {
    const existing = await prisma.campaign.findFirst({ where: { campaignParam: c.param } });
    if (existing) {
      skipped.push(c.param);
      continue;
    }
    await prisma.campaign.create({
      data: {
        name: c.name,
        source: "meta",
        medium: "paid_social",
        campaignParam: c.param,
        landingSlug: "love",
        assessmentId: love.id,
        creativeName: c.creative,
        status: "active",
      },
    });
    created.push(c.param);
  }

  return NextResponse.json({ ok: true, created, skipped });
}
