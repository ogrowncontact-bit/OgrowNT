import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { confirmKillSwitchRecovery } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { force } = await request.json().catch(() => ({ force: false }));

  const result = await confirmKillSwitchRecovery(token, Boolean(force));
  if (!result) return NextResponse.json({ detail: "Recovery confirm failed" }, { status: 502 });
  return NextResponse.json(result);
}
