import { prisma } from "@inner/db";
import { renderCheckoutReminderEmail, renderRecommendationNudgeEmail } from "@inner/email";
import { getEmailProvider } from "./email";
import { getAssessmentConfig } from "./assessments";
import { selectRecommendation } from "./recommendation";
import { signToken } from "./security/signedToken";
import { recordEmailEvent } from "./emailEvents";

/**
 * Growth tooling per docs/ARCHITECTURE.md §6/§11. Meant to be invoked
 * periodically (see app/api/admin/jobs/reengagement/route.ts for how a real
 * deployment wires this to a scheduler) — not a long-running process itself.
 *
 * Only targets people we already have an email for (checkout was reached),
 * per §the doc's own note that recovering someone who never finishes — and
 * so never gave an email — isn't solvable by email at all with the current
 * no-forced-account design.
 */

function appBaseUrl(): string {
  return process.env.APP_BASE_URL ?? "http://localhost:3000";
}

const CHECKOUT_REMINDER_DELAY_MS = 60 * 60 * 1000; // 1h after checkout_started with no payment
const CHECKOUT_REMINDER_COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000; // don't re-remind the same person more than once a week
const RECOMMENDATION_NUDGE_DELAY_MS = 24 * 60 * 60 * 1000; // 1 day after a purchase

export interface ReengagementCounts {
  sent: number;
  skipped: number;
}

export interface ReengagementRunResult {
  checkoutReminders: ReengagementCounts;
  recommendationNudges: ReengagementCounts;
}

export async function runReengagementBatch(now: Date = new Date()): Promise<ReengagementRunResult> {
  const [checkoutReminders, recommendationNudges] = await Promise.all([
    sendCheckoutReminders(now),
    sendRecommendationNudges(now),
  ]);
  return { checkoutReminders, recommendationNudges };
}

async function sendCheckoutReminders(now: Date): Promise<ReengagementCounts> {
  const counts: ReengagementCounts = { sent: 0, skipped: 0 };
  const cutoff = new Date(now.getTime() - CHECKOUT_REMINDER_DELAY_MS);

  const pendingOrders = await prisma.order.findMany({
    where: { status: "pending", createdAt: { lt: cutoff } },
    include: { user: true, price: { include: { assessment: true } }, assessmentSession: true },
    orderBy: { createdAt: "asc" },
  });

  for (const order of pendingOrders) {
    const recentReminder = await prisma.emailEvent.findFirst({
      where: {
        userId: order.userId,
        type: "checkout_reminder",
        sentAt: { gt: new Date(now.getTime() - CHECKOUT_REMINDER_COOLDOWN_MS) },
      },
    });
    if (recentReminder) {
      counts.skipped++;
      continue;
    }

    // Per FASE 30's abandoned-checkout rule: this is a proactive recovery
    // nudge, not a transactional payment-status notice (that's
    // markOrderCancelled's payment_failed email, sent immediately on a
    // specific expiry event and left ungated) — so it follows the same
    // consent gate sendRecommendationNudges below already applies.
    const consent = await prisma.marketingConsent.findFirst({
      where: { userId: order.userId },
      orderBy: { consentTimestamp: "desc" },
    });
    if (!consent?.consent) {
      counts.skipped++;
      continue;
    }

    const unsubscribed = await prisma.unsubscribe.findFirst({ where: { userId: order.userId } });
    if (unsubscribed) {
      counts.skipped++;
      continue;
    }

    const checkoutUrl = `${appBaseUrl()}/${order.assessmentSession.sourceSlug}/session/${order.assessmentSessionId}/checkout`;
    const provider = getEmailProvider();
    const result = await provider.send({
      to: order.user.email,
      subject: `${order.price.assessment.name} — your profile is ready to unlock`,
      html: renderCheckoutReminderEmail({
        assessmentName: order.price.assessment.name,
        priceLabel: `${(order.amountCents / 100).toFixed(2)} ${order.currency}`,
        checkoutUrl,
      }),
    });

    await recordEmailEvent({
      userId: order.userId,
      type: "checkout_reminder",
      templateKey: "checkout_reminder_v1",
      providerRef: result.providerRef,
      relatedEntityId: order.id,
      status: result.ok ? "sent" : "failed",
    });
    if (result.ok) counts.sent++;
    else counts.skipped++;
  }

  return counts;
}

async function sendRecommendationNudges(now: Date): Promise<ReengagementCounts> {
  const counts: ReengagementCounts = { sent: 0, skipped: 0 };
  const cutoff = new Date(now.getTime() - RECOMMENDATION_NUDGE_DELAY_MS);

  const entitlements = await prisma.entitlement.findMany({
    where: { grantedAt: { lt: cutoff } },
    include: { user: true, assessmentSession: { include: { assessment: true } } },
    orderBy: { grantedAt: "asc" },
  });

  for (const entitlement of entitlements) {
    const alreadyNudged = await prisma.emailEvent.findFirst({
      where: { userId: entitlement.userId, type: "recommendation_nudge" },
    });
    if (alreadyNudged) {
      counts.skipped++;
      continue;
    }

    const consent = await prisma.marketingConsent.findFirst({
      where: { userId: entitlement.userId },
      orderBy: { consentTimestamp: "desc" },
    });
    if (!consent?.consent) {
      counts.skipped++;
      continue;
    }

    const unsubscribed = await prisma.unsubscribe.findFirst({ where: { userId: entitlement.userId } });
    if (unsubscribed) {
      counts.skipped++;
      continue;
    }

    const session = entitlement.assessmentSession;
    const [config, profileResult, dimensionScoreRows] = await Promise.all([
      getAssessmentConfig(session.sourceSlug),
      prisma.profileResult.findUnique({ where: { assessmentSessionId: session.id } }),
      prisma.dimensionScore.findMany({ where: { assessmentSessionId: session.id } }),
    ]);
    if (!config || !profileResult) {
      counts.skipped++;
      continue;
    }

    const primary = config.profiles.find((p) => p.key === profileResult.primaryProfileKey);
    const dimensionScores = Object.fromEntries(dimensionScoreRows.map((d) => [d.dimensionKey, d.normalizedScore]));

    const recommendation = await selectRecommendation({
      anonymousSessionId: session.anonymousSessionId,
      fromConfig: config,
      primaryProfileName: primary?.name ?? "",
      dimensionScores,
    });
    if (!recommendation) {
      counts.skipped++;
      continue;
    }

    const unsubscribeUrl = `${appBaseUrl()}/unsubscribe?token=${signToken({ userId: entitlement.userId })}`;
    const provider = getEmailProvider();
    const result = await provider.send({
      to: entitlement.user.email,
      subject: `Since you explored ${config.name}...`,
      html: renderRecommendationNudgeEmail({
        fromAssessmentName: config.name,
        targetAssessmentName: recommendation.name,
        bridgeCopy: recommendation.bridgeCopy,
        targetUrl: `${appBaseUrl()}/${recommendation.slug}`,
        unsubscribeUrl,
      }),
    });

    await recordEmailEvent({
      userId: entitlement.userId,
      type: "recommendation_nudge",
      templateKey: "recommendation_nudge_v1",
      transactional: false, // the one genuinely marketing-flagged send — gated on consent + Unsubscribe above
      providerRef: result.providerRef,
      relatedEntityId: entitlement.id,
      status: result.ok ? "sent" : "failed",
    });
    if (result.ok) counts.sent++;
    else counts.skipped++;
  }

  return counts;
}
