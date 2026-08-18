import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { setKillSwitch } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { action } = await request.json();
  if (action !== "trigger" && action !== "release") {
    return NextResponse.json({ detail: "Invalid action" }, { status: 400 });
  }

  const result = await setKillSwitch(token, action);
  if (!result) return NextResponse.json({ detail: "Kill switch action failed" }, { status: 502 });
  return NextResponse.json(result);
}
