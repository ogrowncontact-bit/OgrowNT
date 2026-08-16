import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { runReengagementBatch } from "@/lib/reengagement";

function isValidCronAuth(authHeader: string | null, cronSecret: string | undefined): boolean {
  if (!cronSecret || !authHeader) return false;
  const expected = Buffer.from(`Bearer ${cronSecret}`);
  const actual = Buffer.from(authHeader);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

/**
 * Runs the re-engagement batch (checkout reminders + post-purchase
 * recommendation nudges). Two ways in, so this works both as an
 * admin-triggered manual run and as a real scheduled job:
 *
 *  - An admin session cookie (the "Run now" button in /admin/analytics).
 *  - `Authorization: Bearer <CRON_SECRET>`, for an external scheduler
 *    (Vercel Cron, a systemd timer, etc.) hitting this route periodically.
 *    Only enabled when CRON_SECRET is set — unset means cron access is off,
 *    not open.
 */
export async function POST(request: NextRequest) {
  const isCronCall = isValidCronAuth(request.headers.get("authorization"), process.env.CRON_SECRET);

  if (!isCronCall) {
    await requireAdminWriter();
  }

  const result = await runReengagementBatch();
  return NextResponse.json(result);
}
