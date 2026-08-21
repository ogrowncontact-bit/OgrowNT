import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { startKillSwitchRecovery } from "@/lib/api";

export async function POST() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const result = await startKillSwitchRecovery(token);
  if (!result) return NextResponse.json({ detail: "Recovery start failed" }, { status: 502 });
  return NextResponse.json(result);
}
