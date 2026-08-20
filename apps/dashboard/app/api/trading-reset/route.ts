import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { resetPaperAccount } from "@/lib/api";

export async function POST() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const result = await resetPaperAccount(token, true);
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 502 });
  return NextResponse.json(result.result);
}
