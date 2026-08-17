import { NextRequest, NextResponse } from "next/server";
import { requestAccessLink } from "@/lib/access";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const email = (body?.email as string | undefined)?.trim().toLowerCase();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: "A valid email is required" }, { status: 400 });
  }

  await requestAccessLink(email);

  // Always the same response whether or not we found anything to send.
  return NextResponse.json({ ok: true });
}
