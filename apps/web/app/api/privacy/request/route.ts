import { NextRequest, NextResponse } from "next/server";
import { requestPrivacyAction } from "@/lib/privacy";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const email = (body?.email as string | undefined)?.trim().toLowerCase();
  const action = body?.action as string | undefined;

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || (action !== "export" && action !== "delete")) {
    return NextResponse.json({ error: "A valid email and action are required" }, { status: 400 });
  }

  await requestPrivacyAction(email, action);

  // Always the same response whether or not the email is on file.
  return NextResponse.json({ ok: true });
}
