import { NextRequest, NextResponse } from "next/server";
import { readAccessUserId } from "@/lib/access";
import { setMarketingPreference } from "@/lib/preferences";

export async function POST(request: NextRequest) {
  const userId = await readAccessUserId();
  if (!userId) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

  const body = await request.json().catch(() => null);
  if (typeof body?.subscribed !== "boolean") {
    return NextResponse.json({ error: "subscribed must be a boolean" }, { status: 400 });
  }

  await setMarketingPreference(userId, body.subscribed);
  return NextResponse.json({ ok: true });
}
