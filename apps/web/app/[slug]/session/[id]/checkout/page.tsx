import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { CheckoutForm } from "@/components/CheckoutForm";

export default async function CheckoutPage({ params }: { params: Promise<{ slug: string; id: string }> }) {
  const { slug, id } = await params;

  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) redirect(`/${slug}`);

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) notFound();
  if (session.status !== "completed") redirect(`/${slug}/session/${id}`);

  const config = getAssessmentConfig(session.sourceSlug);
  if (!config) notFound();

  // Already purchased — go straight to the report instead of charging again.
  const existingEntitlement = await prisma.entitlement.findFirst({ where: { assessmentSessionId: id } });
  if (existingEntitlement) redirect(`/${slug}/session/${id}/report`);

  const price = config.pricing.individual;

  return <CheckoutForm slug={slug} assessmentSessionId={id} priceLabel={price ? `€${(price.amountCents / 100).toFixed(2)}` : ""} />;
}
