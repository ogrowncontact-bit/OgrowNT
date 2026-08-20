import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { pauseTrading, resumeTrading } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { action, reason } = await request.json();
  if (action !== "pause" && action !== "resume") {
    return NextResponse.json({ detail: "Invalid action" }, { status: 400 });
  }

  const result =
    action === "pause" ? await pauseTrading(token, reason ?? "") : await resumeTrading(token);
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 502 });
  return NextResponse.json(result.result);
}
