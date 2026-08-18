import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { runBacktest, type RunBacktestPayload } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const payload = (await request.json()) as RunBacktestPayload;
  const result = await runBacktest(token, payload);
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 502 });
  return NextResponse.json(result.result);
}
