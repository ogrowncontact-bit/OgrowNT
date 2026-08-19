import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { createFullLabJob, type FullLabJobPayload } from "@/lib/api";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const payload = (await request.json()) as FullLabJobPayload;
  const result = await createFullLabJob(token, payload);
  if (!result.ok) return NextResponse.json({ detail: result.detail }, { status: 502 });
  return NextResponse.json(result.job);
}
