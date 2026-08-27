import { cookies, headers } from "next/headers";
import { prisma } from "@inner/db";
import { hashIdentifier, signSessionToken, verifySessionToken } from "./security/sessionToken";
import { classifyDeviceType } from "./deviceDetection";

export const SESSION_COOKIE = "inner_sid";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180; // 180 days

export interface Utm {
  utmSource?: string;
  utmMedium?: string;
  utmCampaign?: string;
  utmContent?: string;
  utmTerm?: string;
}

/** Reads the anonymous session id from the signed cookie, if present and valid. No DB access. */
export async function readAnonymousSessionId(): Promise<string | null> {
  const jar = await cookies();
  return verifySessionToken(jar.get(SESSION_COOKIE)?.value);
}

/**
 * Route-handler-only: returns the existing anonymous session, or creates one
 * (DB row + signed cookie) on first contact. `firstLandingSlug`/`utm` are
 * only recorded on creation — we never overwrite a user's original
 * acquisition attribution on a later visit.
 */
export async function ensureAnonymousSession(params: { firstLandingSlug: string; utm?: Utm }): Promise<string> {
  const existing = await readAnonymousSessionId();
  if (existing) {
    const row = await prisma.anonymousSession.findUnique({ where: { id: existing } });
    if (row) {
      await prisma.anonymousSession.update({ where: { id: existing }, data: { lastSeenAt: new Date() } });
      return existing;
    }
  }

  const h = await headers();
  const ip = h.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const ua = h.get("user-agent") ?? "unknown";
  const referrer = h.get("referer") ?? undefined;

  const created = await prisma.anonymousSession.create({
    data: {
      firstLandingSlug: params.firstLandingSlug,
      utmSource: params.utm?.utmSource,
      utmMedium: params.utm?.utmMedium,
      utmCampaign: params.utm?.utmCampaign,
      utmContent: params.utm?.utmContent,
      utmTerm: params.utm?.utmTerm,
      referrer,
      ipHash: hashIdentifier(ip),
      uaHash: hashIdentifier(ua),
      deviceType: classifyDeviceType(ua),
    },
  });

  const jar = await cookies();
  jar.set(SESSION_COOKIE, signSessionToken(created.id), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: COOKIE_MAX_AGE_SECONDS,
  });

  return created.id;
}
