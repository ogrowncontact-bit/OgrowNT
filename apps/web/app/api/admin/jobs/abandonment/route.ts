import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { detectAbandonedSessions } from "@/lib/assessmentAbandonment";

function isValidCronAuth(authHeader: string | null, cronSecret: string | undefined): boolean {
  if (!cronSecret || !authHeader) return false;
  const expected = Buffer.from(`Bearer ${cronSecret}`);
  const actual = Buffer.from(authHeader);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

/**
 * Runs the assessment-abandonment sweep. Same dual-auth shape as
 * app/api/admin/jobs/reengagement/route.ts: an admin session cookie (the
 * "Run now" button in /admin/analytics), or `Authorization: Bearer
 * <CRON_SECRET>` for an external scheduler.
 */
export async function POST(request: NextRequest) {
  const isCronCall = isValidCronAuth(request.headers.get("authorization"), process.env.CRON_SECRET);

  if (!isCronCall) {
    await requireAdminWriter();
  }

  const result = await detectAbandonedSessions();
  return NextResponse.json(result);
}
