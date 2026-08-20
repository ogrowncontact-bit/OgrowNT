import type { Metadata } from "next";
import Link from "next/link";
import { Screen } from "@inner/ui";
import { PublicNav } from "@/components/PublicNav";
import { listPublishedJournalPosts } from "@/lib/journal";
import { getSiteUrl } from "@/lib/siteUrl";

const title = "Journal";
const description = "Short reads on the patterns INNER explores — connection, communication, decision-making, and how people relate.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: `${getSiteUrl()}/journal` },
  openGraph: { title, description, url: `${getSiteUrl()}/journal`, type: "website" },
  twitter: { card: "summary_large_image", title, description },
};

export const dynamic = "force-dynamic";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium" }).format(d);
}

export default async function JournalIndexPage() {
  const posts = await listPublishedJournalPosts();

  return (
    <Screen align="top" eyebrow={<PublicNav />}>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-[var(--inner-muted)]">Journal</p>
      <h1 className="font-display text-[28px] leading-tight text-[var(--inner-ink)]">
        Notes on patterns, not prescriptions.
      </h1>

      <div className="mb-16 mt-8 space-y-4">
        {posts.map((post) => (
          <Link
            key={post.slug}
            href={`/journal/${post.slug}`}
            className="block rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5"
          >
            <p className="text-[12px] text-[var(--inner-muted)]">{formatDate(post.publishedAt)}</p>
            <h2 className="font-display mt-1 text-[19px] text-[var(--inner-ink)]">{post.title}</h2>
            <p className="mt-2 text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{post.excerpt}</p>
          </Link>
        ))}
        {posts.length === 0 && (
          <p className="text-[14px] text-[var(--inner-muted)]">Nothing published here yet — check back soon.</p>
        )}
      </div>
    </Screen>
  );
}
