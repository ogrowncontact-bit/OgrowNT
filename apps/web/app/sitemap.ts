import type { MetadataRoute } from "next";
import { listPublishedSlugs } from "@/lib/assessments";
import { listPublishedJournalPosts } from "@/lib/journal";
import { getSiteUrl } from "@/lib/siteUrl";

// Forced dynamic for the same reason /explore and the homepage are: this
// reads the catalog, and newly published experiences need to show up here
// immediately rather than waiting for the next build/deploy.
export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const siteUrl = getSiteUrl();
  const [slugs, journalPosts] = await Promise.all([listPublishedSlugs(), listPublishedJournalPosts()]);

  const assessmentEntries: MetadataRoute.Sitemap = slugs.map((slug) => ({
    url: `${siteUrl}/${slug}`,
    changeFrequency: "monthly",
    priority: 0.8,
  }));

  const journalEntries: MetadataRoute.Sitemap = journalPosts.map((post) => ({
    url: `${siteUrl}/journal/${post.slug}`,
    lastModified: post.publishedAt,
    changeFrequency: "monthly",
    priority: 0.5,
  }));

  const staticEntries: MetadataRoute.Sitemap = [
    { url: siteUrl, changeFrequency: "weekly", priority: 1 },
    { url: `${siteUrl}/explore`, changeFrequency: "weekly", priority: 0.7 },
    { url: `${siteUrl}/how-it-works`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${siteUrl}/about`, changeFrequency: "monthly", priority: 0.4 },
    { url: `${siteUrl}/journal`, changeFrequency: "weekly", priority: 0.5 },
    { url: `${siteUrl}/terms`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${siteUrl}/privacy-policy`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${siteUrl}/cookies`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${siteUrl}/refund`, changeFrequency: "yearly", priority: 0.2 },
  ];

  return [...staticEntries, ...assessmentEntries, ...journalEntries];
}
