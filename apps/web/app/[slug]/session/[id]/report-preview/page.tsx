import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { Screen, Button } from "@inner/ui";
import type { ReportDocumentSection } from "@inner/ai";
import type { EnrichedInsight } from "@inner/ai";
import type { TensionResult } from "@inner/assessment-engine";
import { getAssessmentConfig } from "@/lib/assessments";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { track } from "@/lib/analytics";
import { formatPrice } from "@/lib/money";
import { getPremiumPreviewItems } from "@/lib/landingContent";
import { ReportSectionBlock, CARD, EYEBROW } from "@/components/ReportView";

/**
 * FASE 29 §REPORT PREVIEW — sits between the paywall (which lists WHAT the
 * report contains) and checkout, showing 2-3 sections actually rendered in
 * the real report template. Built entirely from data already computed at
 * session completion (aiSemanticNotes.insight/insights, tensions) — no new
 * AI call, no full ReportDocument generation, which stays payment-gated
 * (see lib/commerce.ts). Never the full interpretation, just real proof of
 * what one looks like.
 */
export default async function ReportPreviewPage({ params }: { params: Promise<{ slug: string; id: string }> }) {
  const { slug, id } = await params;

  const anonymousSessionId = await readAnonymousSessionId();
  if (!anonymousSessionId) redirect(`/${slug}`);

  const session = await prisma.assessmentSession.findUnique({ where: { id } });
  if (!session || session.anonymousSessionId !== anonymousSessionId) notFound();
  if (session.status !== "completed") redirect(`/${slug}/session/${id}`);

  const config = await getAssessmentConfig(session.sourceSlug);
  if (!config) notFound();

  const existingEntitlement = await prisma.entitlement.findFirst({ where: { assessmentSessionId: id } });
  if (existingEntitlement) redirect(`/${slug}/session/${id}/report`);

  const profileResult = await prisma.profileResult.findUnique({ where: { assessmentSessionId: id } });
  if (!profileResult) redirect(`/${slug}/session/${id}/paywall`);

  const primary = config.profiles.find((p) => p.key === profileResult.primaryProfileKey);
  if (!primary) notFound();

  const aiNotes = profileResult.aiSemanticNotes as { insight?: string; insights?: EnrichedInsight[] } | null;
  const tensions = (profileResult.tensions as TensionResult[] | null) ?? [];
  const topTension = [...tensions].sort((a, b) => b.strength - a.strength)[0];
  const strengthInsight = aiNotes?.insights?.find((i) => i.type === "strength" || i.type === "pattern");

  const previewSections: ReportDocumentSection[] = [
    {
      key: "core_pattern_preview",
      title: "Your Core Pattern",
      body: aiNotes?.insight || primary.descriptionTemplate,
      aiGenerated: Boolean(aiNotes?.insight),
      role: "core_pattern",
    },
    ...(strengthInsight
      ? ([
          {
            key: "strength_preview",
            title: "A Strength We Noticed",
            body: strengthInsight.text,
            aiGenerated: true,
            role: "strengths",
          } satisfies ReportDocumentSection,
        ] as ReportDocumentSection[])
      : []),
    ...(topTension
      ? ([
          {
            key: "tension_preview",
            title: "A Tension Worth Noticing",
            body: topTension.label,
            aiGenerated: false,
            role: "tension",
          } satisfies ReportDocumentSection,
        ] as ReportDocumentSection[])
      : []),
  ];

  const previewItems = getPremiumPreviewItems(config);
  const price = config.pricing.individual;

  await track({ anonymousSessionId, eventName: "report_preview_viewed", assessmentId: session.assessmentId });

  return (
    <Screen
      align="top"
      footer={
        <Link href={`/${slug}/session/${id}/checkout`}>
          <Button>
            {price ? `Unlock My Full Report — ${formatPrice(price.amountCents, price.currency)}` : "Unlock My Full Report"}
          </Button>
        </Link>
      }
    >
      <p className={EYEBROW}>A preview of your report</p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">{primary.name}</h1>
      <p className="mt-3 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">
        This is what a section of your real report actually looks like — built from your own answers, not a generic
        template.
      </p>

      <div className="mt-8 space-y-6">
        {previewSections.map((section) => (
          <ReportSectionBlock key={section.key} section={section} />
        ))}
      </div>

      <div className={`${CARD} mt-8`}>
        <p className={EYEBROW}>Still locked</p>
        <p className="text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">
          {previewItems.length} more section{previewItems.length === 1 ? "" : "s"} — including {previewItems.slice(0, 3).join(", ")}
          {previewItems.length > 3 ? ", and more" : ""} — unlock with your full report.
        </p>
      </div>
    </Screen>
  );
}
