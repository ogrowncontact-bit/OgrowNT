import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { closePaperPosition } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { positionId, reason } = await request.json();
  if (typeof positionId !== "number") {
    return NextResponse.json({ detail: "Invalid positionId" }, { status: 400 });
  }

  const result = await closePaperPosition(token, positionId, reason ?? null);
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 502 });
  return NextResponse.json(result.result);
}
