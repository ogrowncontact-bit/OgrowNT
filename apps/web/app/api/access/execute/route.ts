import { NextRequest, NextResponse } from "next/server";
import { verifyAccessLinkToken, grantAccessCookie } from "@/lib/access";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const token = body?.token as string | undefined;
  const payload = verifyAccessLinkToken(token);
  if (!payload) {
    return NextResponse.json({ error: "This link is invalid or has expired." }, { status: 400 });
  }

  await grantAccessCookie(payload.userId);

  return NextResponse.json({ ok: true });
}
