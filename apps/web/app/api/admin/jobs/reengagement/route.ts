import { NextRequest, NextResponse } from "next/server";
import { requireAdminWriter } from "@/lib/adminAuth";
import { runReengagementBatch } from "@/lib/reengagement";

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
  const cronSecret = process.env.CRON_SECRET;
  const authHeader = request.headers.get("authorization");
  const isCronCall = Boolean(cronSecret) && authHeader === `Bearer ${cronSecret}`;

  if (!isCronCall) {
    await requireAdminWriter();
  }

  const result = await runReengagementBatch();
  return NextResponse.json(result);
}
