import { NextRequest, NextResponse } from "next/server";
import { verifyAccessLinkToken, consumeAccessToken, grantAccessCookie } from "@/lib/access";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const token = body?.token as string | undefined;
  const payload = verifyAccessLinkToken(token);
  if (!payload || !token) {
    return NextResponse.json({ error: "This link is invalid or has expired." }, { status: 400 });
  }

  const claimed = await consumeAccessToken(token);
  if (!claimed) {
    return NextResponse.json({ error: "This link is invalid or has expired." }, { status: 400 });
  }

  await grantAccessCookie(payload.userId);

  const anonymousSessionId = await readAnonymousSessionId();
  if (anonymousSessionId) {
    await track({ anonymousSessionId, eventName: "magic_link_used", userId: payload.userId });
  }

  return NextResponse.json({ ok: true });
}
