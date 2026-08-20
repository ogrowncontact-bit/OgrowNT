import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { restoreAgent } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { code } = await request.json();
  if (typeof code !== "string" || !code) {
    return NextResponse.json({ detail: "Invalid agent code" }, { status: 400 });
  }

  const result = await restoreAgent(token, code);
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 502 });
  return NextResponse.json(result.result);
}
