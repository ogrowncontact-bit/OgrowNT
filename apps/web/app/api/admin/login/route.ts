import { NextRequest, NextResponse } from "next/server";
import { loginAdmin } from "@/lib/adminAuth";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const email = body?.email as string | undefined;
  const password = body?.password as string | undefined;
  if (!email || !password) return NextResponse.json({ error: "Email and password are required" }, { status: 400 });

  const session = await loginAdmin(email, password);
  if (!session) return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });

  return NextResponse.json({ ok: true });
}
