import { NextResponse } from "next/server";
import { ensureAnonymousSession } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

/**
 * Same shape as /api/events/landing-view — /explore is itself an entry
 * point (a visitor can land here directly, with no prior /[slug] visit and
 * so no anonymous session cookie yet), so this bootstraps one rather than
 * silently dropping the event the way the generic /api/events beacon does
 * for a missing session.
 */
export async function POST() {
  const anonymousSessionId = await ensureAnonymousSession({ firstLandingSlug: "explore" });
  await track({ anonymousSessionId, eventName: "explore_opened" });
  return NextResponse.json({ ok: true });
}
