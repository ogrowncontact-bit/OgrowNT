import { createHash } from "node:crypto";
import { cookies } from "next/headers";
import { prisma, Prisma } from "@inner/db";
import { renderAccessLinkEmail } from "@inner/email";
import { getEmailProvider } from "./email";
import { signToken, verifyToken } from "./security/signedToken";
import { recordEmailEvent } from "./emailEvents";
import { checkRateLimit } from "./security/rateLimit";

/**
 * Magic-link report access: lets a returning user reach every past report,
 * not just the one on the device/browser they purchased from. Same
 * double-opt-in shape as lib/privacy.ts (the email only ever carries a link
 * to a confirm page — a GET that granted access immediately would let an
 * email security scanner's pre-fetch silently log an attacker's cookie
 * jar in, so the actual grant only happens on the confirm page's POST).
 *
 * Deliberately a separate cookie from the anonymous session
 * (lib/anonymousSession.ts) rather than overwriting it — granting access
 * shouldn't reassign whichever anonymous session happens to be live in this
 * browser, and a user may want both (their current in-progress assessment
 * and read access to old reports) at once.
 */

export const ACCESS_COOKIE = "inner_access";
const LINK_TTL_MS = 30 * 60 * 1000;
const ACCESS_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180; // matches SESSION_COOKIE in anonymousSession.ts
const REQUEST_RATE_LIMIT = { maxAttempts: 5, windowMs: 15 * 60 * 1000 }; // 5 requests / 15min per email, regardless of whether it's on file

interface AccessTokenPayload extends Record<string, string> {
  userId: string;
}

function appBaseUrl(): string {
  return process.env.APP_BASE_URL ?? "http://localhost:3000";
}

/**
 * Always resolves the same way whether or not the email is on file (see
 * lib/privacy.ts for the same reasoning) — but the rate limit itself is
 * checked first and applies regardless, since a flood of requests for an
 * email that doesn't exist is just as much abuse as one that does.
 */
export async function requestAccessLink(email: string): Promise<{ rateLimited: boolean }> {
  const normalized = email.trim().toLowerCase();
  const { allowed } = await checkRateLimit("access_link_request", normalized, REQUEST_RATE_LIMIT);
  if (!allowed) return { rateLimited: true };

  const user = await prisma.user.findUnique({ where: { email: normalized } });
  if (!user) return { rateLimited: false };

  const token = signToken({ userId: user.id }, LINK_TTL_MS);
  const confirmUrl = `${appBaseUrl()}/access/confirm?token=${token}`;

  const result = await getEmailProvider().send({
    to: user.email,
    subject: "Access your INNER reports",
    html: renderAccessLinkEmail({ confirmUrl }),
  });
  await recordEmailEvent({
    userId: user.id,
    type: "magic_link",
    templateKey: "access_link_v1",
    providerRef: result.providerRef,
    status: result.ok ? "sent" : "failed",
  });

  return { rateLimited: false };
}

export function verifyAccessLinkToken(token: string | undefined | null): AccessTokenPayload | null {
  return verifyToken<AccessTokenPayload>(token);
}

function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

/**
 * Single-use enforcement for an already-verified (so already known
 * unexpired) token: atomically claims it via a unique-constraint insert, so
 * a concurrent or replayed request for the exact same token loses the
 * race. Only the token's hash is ever stored, retained for one more TTL
 * window past the moment it's consumed — long enough to outlive the
 * token's own remaining validity, short enough not to accumulate forever.
 */
export async function consumeAccessToken(token: string): Promise<boolean> {
  try {
    await prisma.usedAccessToken.create({
      data: { tokenHash: hashToken(token), expiresAt: new Date(Date.now() + LINK_TTL_MS) },
    });
    // Opportunistic cleanup — best-effort, never blocks the actual grant on failure.
    await prisma.usedAccessToken.deleteMany({ where: { expiresAt: { lt: new Date() } } }).catch(() => {});
    return true;
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === "P2002") return false;
    throw error;
  }
}

/** Route-handler-only: called from the confirm page's POST, after the token has already been verified and consumed. */
export async function grantAccessCookie(userId: string): Promise<void> {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, signToken({ userId }, ACCESS_COOKIE_MAX_AGE_SECONDS * 1000), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: ACCESS_COOKIE_MAX_AGE_SECONDS,
  });
  await prisma.user.update({ where: { id: userId }, data: { lastSeenAt: new Date() } });
}

/** Reads the access-granted user id from the signed cookie, if present and valid. No DB access. */
export async function readAccessUserId(): Promise<string | null> {
  const jar = await cookies();
  const payload = verifyToken<AccessTokenPayload>(jar.get(ACCESS_COOKIE)?.value);
  return payload?.userId ?? null;
}
