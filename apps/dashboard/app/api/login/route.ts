import { NextResponse } from "next/server";
import { login } from "@/lib/api";

const COOKIE_NAME = "ogrownt_token";

export async function POST(request: Request) {
  const { email, password } = await request.json();
  const result = await login(email, password);

  if (!result) {
    return NextResponse.json({ detail: "Invalid credentials" }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(COOKIE_NAME, result.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    expires: new Date(result.expires_at),
    path: "/",
  });
  return response;
}
