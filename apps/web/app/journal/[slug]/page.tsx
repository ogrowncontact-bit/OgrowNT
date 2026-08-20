import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Screen } from "@inner/ui";
import { PublicNav } from "@/components/PublicNav";
import { getPublishedJournalPost } from "@/lib/journal";
import { getSiteUrl } from "@/lib/siteUrl";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPublishedJournalPost(slug);
  if (!post) return {};

  const url = `${getSiteUrl()}/journal/${slug}`;
  return {
    title: post.title,
    description: post.excerpt,
    alternates: { canonical: url },
    openGraph: { title: post.title, description: post.excerpt, url, type: "article" },
    twitter: { card: "summary_large_image", title: post.title, description: post.excerpt },
  };
}

export default async function JournalPostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await getPublishedJournalPost(slug);
  if (!post) notFound();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.excerpt,
    datePublished: post.publishedAt.toISOString(),
    author: { "@type": "Organization", name: "INNER" },
  };

  const paragraphs = post.body.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);

  return (
    <Screen align="top" eyebrow={<PublicNav />}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Journal</p>
      <h1 className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">{post.title}</h1>
      <p className="mt-2 text-[13px] text-[var(--inner-muted)]">
        {new Intl.DateTimeFormat("en-IE", { dateStyle: "medium" }).format(post.publishedAt)}
      </p>

      <div className="mb-16 mt-8 space-y-4 text-[15px] leading-relaxed text-[var(--inner-ink-soft)]">
        {paragraphs.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
    </Screen>
  );
}
