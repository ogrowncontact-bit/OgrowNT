import { prisma } from "@inner/db";

/**
 * Blog foundation (FASE 23 §BLOG FOUNDATION) — CMS + template only. Public
 * reads only ever see published posts, same status-gating pattern as
 * getAssessmentConfig() in lib/assessments.ts.
 */
export interface JournalPostSummary {
  slug: string;
  title: string;
  excerpt: string;
  publishedAt: Date;
}

export interface JournalPostDetail extends JournalPostSummary {
  body: string;
}

export async function listPublishedJournalPosts(): Promise<JournalPostSummary[]> {
  const rows = await prisma.journalPost.findMany({
    where: { status: "published" },
    orderBy: { publishedAt: "desc" },
    select: { slug: true, title: true, excerpt: true, publishedAt: true },
  });
  return rows.map((r) => ({ ...r, publishedAt: r.publishedAt! }));
}

export async function getPublishedJournalPost(slug: string): Promise<JournalPostDetail | null> {
  const row = await prisma.journalPost.findUnique({ where: { slug } });
  if (!row || row.status !== "published" || !row.publishedAt) return null;
  return { slug: row.slug, title: row.title, excerpt: row.excerpt, body: row.body, publishedAt: row.publishedAt };
}
