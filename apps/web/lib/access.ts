import { cookies } from "next/headers";
import { prisma } from "@inner/db";
import { renderAccessLinkEmail } from "@inner/email";
import { getEmailProvider } from "./email";
import { signToken, verifyToken } from "./security/signedToken";

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

interface AccessTokenPayload extends Record<string, string> {
  userId: string;
}

function appBaseUrl(): string {
  return process.env.APP_BASE_URL ?? "http://localhost:3000";
}

/** Always resolves the same way whether or not the email is on file — see lib/privacy.ts for the same reasoning. */
export async function requestAccessLink(email: string): Promise<void> {
  const user = await prisma.user.findUnique({ where: { email: email.trim().toLowerCase() } });
  if (!user) return;

  const token = signToken({ userId: user.id }, LINK_TTL_MS);
  const confirmUrl = `${appBaseUrl()}/access/confirm?token=${token}`;

  await getEmailProvider().send({
    to: user.email,
    subject: "Access your INNER reports",
    html: renderAccessLinkEmail({ confirmUrl }),
  });
}

export function verifyAccessLinkToken(token: string | undefined | null): AccessTokenPayload | null {
  return verifyToken<AccessTokenPayload>(token);
}

/** Route-handler-only: called from the confirm page's POST, after the token has already been verified. */
export async function grantAccessCookie(userId: string): Promise<void> {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, signToken({ userId }, ACCESS_COOKIE_MAX_AGE_SECONDS * 1000), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: ACCESS_COOKIE_MAX_AGE_SECONDS,
  });
}

/** Reads the access-granted user id from the signed cookie, if present and valid. No DB access. */
export async function readAccessUserId(): Promise<string | null> {
  const jar = await cookies();
  const payload = verifyToken<AccessTokenPayload>(jar.get(ACCESS_COOKIE)?.value);
  return payload?.userId ?? null;
}
