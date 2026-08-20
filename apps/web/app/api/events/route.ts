import { NextRequest, NextResponse } from "next/server";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

const ALLOWED_CLIENT_EVENTS = new Set([
  "landing_view",
  "free_result_viewed",
  "paywall_viewed",
  "checkout_started",
  "share_clicked",
  "recommendation_viewed",
  "hero_cta_clicked",
  "scroll_depth",
  "faq_opened",
  "premium_preview_viewed",
]);

/** Lightweight beacon endpoint for client-fired funnel events. Never accepts arbitrary/raw-text properties. */
export async function POST(request: NextRequest) {
  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) return NextResponse.json({ ok: false }, { status: 401 });

  const body = await request.json().catch(() => null);
  const eventName = body?.eventName as string | undefined;
  if (!eventName || !ALLOWED_CLIENT_EVENTS.has(eventName)) {
    return NextResponse.json({ ok: false }, { status: 400 });
  }

  await track({
    anonymousSessionId,
    eventName,
    assessmentId: body?.assessmentId,
    properties: typeof body?.properties === "object" ? body.properties : undefined,
  });

  return NextResponse.json({ ok: true });
}
