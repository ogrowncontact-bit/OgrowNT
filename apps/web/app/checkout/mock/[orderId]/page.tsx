import { notFound } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen } from "@inner/ui";
import { isMockPayments } from "@/lib/payments";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { MockPaymentForm } from "@/components/MockPaymentForm";

// Dev-only stand-in for the Stripe Checkout page — only reachable when no
// real payment provider is configured (see lib/payments.ts). Never a path
// that exists in a deployment with real Stripe keys set.
export default async function MockCheckoutPage({ params }: { params: Promise<{ orderId: string }> }) {
  if (!isMockPayments()) notFound();

  const { orderId } = await params;
  const order = await prisma.order.findUnique({ where: { id: orderId }, include: { assessmentSession: true } });
  if (!order) notFound();

  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId || order.assessmentSession.anonymousSessionId !== anonymousSessionId) notFound();

  const config = await getAssessmentConfig(order.assessmentSession.sourceSlug);
  if (!config) notFound();

  const cancelUrl = `/${order.assessmentSession.sourceSlug}/session/${order.assessmentSessionId}/paywall?payment=failed`;

  return (
    <Screen align="top" footer={<MockPaymentForm orderId={orderId} cancelUrl={cancelUrl} />}>
      <div className="mb-6 rounded-[var(--inner-radius-md)] border border-[var(--inner-accent)] bg-[var(--inner-card)] p-3 text-center text-[13px] font-medium text-[var(--inner-accent)]">
        TEST MODE — no real payment provider is configured
      </div>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Order summary</p>
      <h1 className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">{config.name} — Personal Report</h1>
      <p className="mt-4 text-[28px] font-medium text-[var(--inner-ink)]">
        {(order.amountCents / 100).toFixed(2)} {order.currency}
      </p>
    </Screen>
  );
}
