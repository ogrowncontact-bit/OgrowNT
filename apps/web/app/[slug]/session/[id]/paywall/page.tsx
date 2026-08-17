import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen, Button } from "@inner/ui";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";

const INCLUDED = [
  "Your dominant pattern",
  "Your relationship style",
  "Your strengths",
  "Your potential friction points",
  "Personalized insights",
  "Reflection questions",
  "PDF delivered by email",
];

export default async function PaywallPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string; id: string }>;
  searchParams: Promise<{ payment?: string }>;
}) {
  const { slug, id } = await params;
  const { payment } = await searchParams;
  const paymentFailed = payment === "failed";

  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) redirect(`/${slug}`);

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) notFound();
  if (session.status !== "completed") redirect(`/${slug}/session/${id}`);

  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) notFound();

  const existingEntitlement = await prisma.entitlement.findFirst({ where: { assessmentSessionId: id } });
  if (existingEntitlement) redirect(`/${slug}/session/${id}/report`);

  const price = config.pricing.individual;

  await track({
    anonymousSessionId,
    eventName: paymentFailed ? "payment_failed" : "paywall_viewed",
    assessmentId: session.assessmentId,
  });

  return (
    <Screen
      align="top"
      footer={
        <Link href={`/${slug}/session/${id}/checkout`}>
          <Button>
            {paymentFailed
              ? "Try Again"
              : price
                ? `Unlock My Profile — €${(price.amountCents / 100).toFixed(2)}`
                : "Unlock My Profile"}
          </Button>
        </Link>
      }
    >
      {paymentFailed && (
        <div role="alert" className="mb-6 rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4">
          <p className="text-[15px] font-medium text-[var(--inner-ink)]">Your payment wasn&apos;t completed.</p>
          <p className="mt-1 text-[13px] text-[var(--inner-ink-soft)]">
            Nothing was charged, and your answers are still saved — pick up right where you left off.
          </p>
        </div>
      )}

      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">
        Your Personal Report
      </p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">
        Everything your answers revealed, in one place.
      </h1>

      <ul className="mt-8 space-y-3">
        {INCLUDED.map((item) => (
          <li key={item} className="flex items-start gap-3 text-[16px] text-[var(--inner-ink-soft)]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="mt-0.5 shrink-0" aria-hidden="true">
              <path
                d="M5 13l4 4L19 7"
                stroke="var(--inner-accent)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {item}
          </li>
        ))}
      </ul>
    </Screen>
  );
}
