import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { prisma } from "@inner/db";
import { getAssessmentConfig } from "@/lib/assessments";
import { AssessmentLandingTemplate } from "@/components/AssessmentLandingTemplate";
import { getFaqItems, getLandingContentOverrides } from "@/lib/landingContent";
import { getAssessmentCtaState } from "@/lib/assessmentCtaState";
import { readAnonymousSessionId } from "@/lib/anonymousSession";
import { getSiteUrl } from "@/lib/siteUrl";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const config = await getAssessmentConfig(slug);
  if (!config) return {};
  const landingContent = await getLandingContentOverrides(slug);

  const title = landingContent.headline?.trim() || config.name;
  const description = landingContent.subheadline?.trim() || config.hook;
  const url = `${getSiteUrl()}/${slug}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      title,
      description,
      url,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  };
}

export default async function ExperienceLanding({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const config = await getAssessmentConfig(slug);
  if (!config) notFound();

  const [assessment, landingContent, anonymousSessionId] = await Promise.all([
    prisma.assessment.findUnique({ where: { slug }, select: { id: true } }),
    getLandingContentOverrides(slug),
    readAnonymousSessionId(),
  ]);
  if (!assessment) notFound();

  const ctaState = await getAssessmentCtaState({ anonymousSessionId, slug, assessmentId: assessment.id });

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: getFaqItems(config, landingContent.extraFaqItems).map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      <AssessmentLandingTemplate
        slug={slug}
        assessmentId={assessment.id}
        config={config}
        landingContent={landingContent}
        ctaState={ctaState}
      />
    </>
  );
}
