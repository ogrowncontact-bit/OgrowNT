import { createHmac, timingSafeEqual } from "node:crypto";

// General-purpose signed, optionally-expiring token for links that must
// prove possession of an email inbox without a login system (unsubscribe,
// GDPR export/delete confirmation) — same HMAC approach as sessionToken.ts,
// generalized to carry an arbitrary payload.
const secret = process.env.SESSION_SECRET ?? "dev-only-change-me";

function hmac(value: string): string {
  return createHmac("sha256", secret).update(value).digest("hex");
}

function base64url(input: string): string {
  return Buffer.from(input, "utf8").toString("base64url");
}

export function signToken(payload: Record<string, string>, expiresInMs?: number): string {
  const body = { ...payload, exp: expiresInMs ? String(Date.now() + expiresInMs) : undefined };
  const encoded = base64url(JSON.stringify(body));
  return `${encoded}.${hmac(encoded)}`;
}

export function verifyToken<T extends Record<string, string>>(token: string | undefined | null): T | null {
  if (!token) return null;
  const [encoded, sig] = token.split(".");
  if (!encoded || !sig) return null;

  const expected = hmac(encoded);
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;

  try {
    const payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8")) as T & { exp?: string };
    if (payload.exp && Date.now() > Number(payload.exp)) return null;
    return payload;
  } catch {
    return null;
  }
}
