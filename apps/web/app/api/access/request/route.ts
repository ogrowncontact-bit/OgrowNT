import { NextRequest, NextResponse } from "next/server";
import { requestAccessLink } from "@/lib/access";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const email = (body?.email as string | undefined)?.trim().toLowerCase();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: "A valid email is required" }, { status: 400 });
  }

  await requestAccessLink(email);

  // Best-effort only — a device requesting access may have no anonymous
  // session cookie at all (that's the whole point of the flow), and we
  // don't create one just to log this event.
  const anonymousSessionId = await readAnonymousSessionId();
  if (anonymousSessionId) {
    await track({ anonymousSessionId, eventName: "magic_link_requested" });
  }

  // Always the same response whether or not we found anything to send.
  return NextResponse.json({ ok: true });
}
