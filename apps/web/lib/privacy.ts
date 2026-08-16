import { prisma } from "@inner/db";
import { renderPrivacyConfirmEmail } from "@inner/email";
import { getEmailProvider } from "./email";
import { decryptText } from "./security/encryption";
import { signToken, verifyToken } from "./security/signedToken";

/**
 * Self-serve GDPR export (Art. 20) and deletion (Art. 17) per
 * docs/ARCHITECTURE.md §12. Double opt-in throughout: a request only ever
 * emails a confirmation link; the link lands on a page that asks for an
 * explicit click before anything happens (a GET that acted immediately
 * would be unsafe — email clients and security gateways pre-fetch links).
 * The action (export vs delete) always comes from the signed token payload,
 * never from a separate client-supplied field, so a leaked/replayed export
 * token can't be used to trigger a delete.
 */

export type PrivacyAction = "export" | "delete";

interface PrivacyTokenPayload extends Record<string, string> {
  userId: string;
  action: PrivacyAction;
}

const TOKEN_TTL_MS = 30 * 60 * 1000;

function appBaseUrl(): string {
  return process.env.APP_BASE_URL ?? "http://localhost:3000";
}

/** Always succeeds from the caller's point of view, whether or not the email is on file — avoids confirming account existence to an unauthenticated caller. */
export async function requestPrivacyAction(email: string, action: PrivacyAction): Promise<void> {
  const user = await prisma.user.findUnique({ where: { email: email.trim().toLowerCase() } });
  if (!user) return;

  const token = signToken({ userId: user.id, action }, TOKEN_TTL_MS);
  const confirmUrl = `${appBaseUrl()}/privacy/confirm?token=${token}`;

  await getEmailProvider().send({
    to: user.email,
    subject: action === "delete" ? "Confirm deleting your INNER data" : "Confirm your INNER data export",
    html: renderPrivacyConfirmEmail({ action, confirmUrl }),
  });
}

export function verifyPrivacyToken(token: string | undefined | null): PrivacyTokenPayload | null {
  const payload = verifyToken<PrivacyTokenPayload>(token);
  if (!payload || (payload.action !== "export" && payload.action !== "delete")) return null;
  return payload;
}

export interface PrivacyExport {
  exportedAt: string;
  email: string;
  accountCreatedAt: string;
  anonymousSessions: unknown[];
  assessmentSessions: unknown[];
  orders: unknown[];
  marketingConsent: unknown[];
  unsubscribed: boolean;
}

export async function buildExport(userId: string): Promise<PrivacyExport> {
  const user = await prisma.user.findUniqueOrThrow({ where: { id: userId } });
  const anonymousSessions = await prisma.anonymousSession.findMany({
    where: { userId },
    include: {
      assessmentSessions: {
        include: {
          assessment: true,
          responses: true,
          openResponses: true,
          dimensionScores: true,
          profileResult: true,
          orders: { include: { price: true } },
        },
      },
    },
  });

  const assessmentSessions = anonymousSessions.flatMap((a) =>
    a.assessmentSessions.map((s) => ({
      assessmentName: s.assessment.name,
      slug: s.sourceSlug,
      status: s.status,
      startedAt: s.startedAt,
      completedAt: s.completedAt,
      responses: s.responses.map((r) => ({
        questionId: r.questionId,
        selectedOptionIds: r.selectedOptionIds,
        scaleValue: r.scaleValue,
        answeredAt: r.answeredAt,
      })),
      openResponses: s.openResponses.map((r) => ({
        questionId: r.questionId,
        text: decryptText(r.rawTextEncrypted),
        createdAt: r.createdAt,
      })),
      dimensionScores: Object.fromEntries(s.dimensionScores.map((d) => [d.dimensionKey, d.normalizedScore])),
      primaryProfileKey: s.profileResult?.primaryProfileKey ?? null,
      secondaryProfileKeys: s.profileResult?.secondaryProfileKeys ?? null,
    }))
  );

  const orders = await prisma.order.findMany({
    where: { userId },
    include: { price: { include: { assessment: true } }, assessmentSession: true, reports: true },
  });

  const consents = await prisma.marketingConsent.findMany({ where: { userId }, orderBy: { consentTimestamp: "desc" } });
  const unsubscribed = (await prisma.unsubscribe.count({ where: { userId } })) > 0;

  return {
    exportedAt: new Date().toISOString(),
    email: user.email,
    accountCreatedAt: user.createdAt.toISOString(),
    anonymousSessions: anonymousSessions.map((a) => ({
      createdAt: a.createdAt,
      firstLandingSlug: a.firstLandingSlug,
      utmSource: a.utmSource,
      utmMedium: a.utmMedium,
      utmCampaign: a.utmCampaign,
      referrer: a.referrer,
    })),
    assessmentSessions,
    orders: orders.map((o) => ({
      assessmentName: o.price.assessment.name,
      productType: o.price.productType,
      amountCents: o.amountCents,
      currency: o.currency,
      status: o.status,
      createdAt: o.createdAt,
      paidAt: o.paidAt,
      reportViewUrl:
        o.reports.length > 0 ? `${appBaseUrl()}/${o.assessmentSession.sourceSlug}/session/${o.assessmentSessionId}/report` : null,
    })),
    marketingConsent: consents.map((c) => ({
      consent: c.consent,
      consentTimestamp: c.consentTimestamp,
      consentVersion: c.consentVersion,
      consentSource: c.consentSource,
      campaign: c.campaign,
    })),
    unsubscribed,
  };
}

/**
 * Erasure with a legal-retention carve-out for commerce (§12: "commerce
 * data anonymized-but-retained where tax law requires"). A session that was
 * ever purchased keeps its shell + structured scores (the record of what
 * was sold and delivered) but has its raw open-text answers erased; a
 * session that was never purchased is deleted outright, along with its
 * parent anonymous session once nothing else references it. The User row
 * itself is never deleted (Order.userId is a required FK, and orders must
 * survive) — its email is scrubbed to an unlinkable placeholder instead.
 */
export async function executeDeletion(userId: string): Promise<void> {
  const deletionRequest = await prisma.deletionRequest.create({ data: { userId } });

  const anonymousSessions = await prisma.anonymousSession.findMany({
    where: { userId },
    include: { assessmentSessions: { include: { orders: true } } },
  });

  for (const anon of anonymousSessions) {
    let keepAnonymousSession = false;

    for (const session of anon.assessmentSessions) {
      await prisma.openResponse.deleteMany({ where: { assessmentSessionId: session.id } });

      if (session.orders.length > 0) {
        keepAnonymousSession = true;
        continue; // purchased — keep the shell + structured data as the commerce record
      }

      await prisma.response.deleteMany({ where: { assessmentSessionId: session.id } });
      await prisma.aiFollowup.deleteMany({ where: { assessmentSessionId: session.id } });
      await prisma.dimensionScore.deleteMany({ where: { assessmentSessionId: session.id } });
      await prisma.profileResult.deleteMany({ where: { assessmentSessionId: session.id } });
      await prisma.assessmentSession.delete({ where: { id: session.id } });
    }

    if (!keepAnonymousSession) {
      await prisma.anonymousSession.delete({ where: { id: anon.id } });
    }
  }

  await prisma.marketingConsent.deleteMany({ where: { userId } });
  await prisma.emailEvent.deleteMany({ where: { userId } });
  await prisma.unsubscribe.deleteMany({ where: { userId } });

  await prisma.user.update({
    where: { id: userId },
    data: { email: `deleted-${userId}@deleted.invalid`, stripeCustomerId: null },
  });

  await prisma.deletionRequest.update({
    where: { id: deletionRequest.id },
    data: { status: "completed", completedAt: new Date() },
  });
}
