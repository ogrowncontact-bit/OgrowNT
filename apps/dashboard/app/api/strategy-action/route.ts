import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { strategyAction } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { strategyId, action } = await request.json();
  if (action !== "promote" && action !== "restore") {
    return NextResponse.json({ detail: "Invalid action" }, { status: 400 });
  }
  if (typeof strategyId !== "number") {
    return NextResponse.json({ detail: "Invalid strategyId" }, { status: 400 });
  }

  const result = await strategyAction(token, strategyId, action);
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 502 });
  return NextResponse.json(result.result);
}
