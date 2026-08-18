import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getAssessmentConfig } from "@/lib/assessments";
import { AssessmentLandingTemplate } from "@/components/AssessmentLandingTemplate";
import { getFaqItems } from "@/lib/landingContent";
import { getSiteUrl } from "@/lib/siteUrl";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const config = await getAssessmentConfig(slug);
  if (!config) return {};

  const url = `${getSiteUrl()}/${slug}`;
  return {
    title: config.name,
    description: config.hook,
    alternates: { canonical: url },
    openGraph: {
      title: config.name,
      description: config.hook,
      url,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: config.name,
      description: config.hook,
    },
  };
}

export default async function ExperienceLanding({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const config = await getAssessmentConfig(slug);
  if (!config) notFound();

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: getFaqItems(config).map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      <AssessmentLandingTemplate slug={slug} config={config} />
    </>
  );
}
