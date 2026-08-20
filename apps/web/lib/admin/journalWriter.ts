import { prisma } from "@inner/db";

const SLUG_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

export interface JournalPostInput {
  slug: string;
  title: string;
  excerpt: string;
  body: string;
}

/**
 * Unlike Assessment/PromptTemplate, journal posts have no scoring/AI
 * behavior riding on them — there's no "never silently modify a production
 * X" concern here, so this is a plain in-place editor (create draft, edit
 * freely, publish/unpublish/archive), the same shape any blog CMS uses.
 */
export async function createJournalPost(input: JournalPostInput): Promise<{ id: string }> {
  const slug = input.slug.trim().toLowerCase();
  if (!SLUG_PATTERN.test(slug)) {
    throw new Error('Slug must be lowercase letters, numbers, and hyphens only (e.g. "my-first-post")');
  }
  const existing = await prisma.journalPost.findUnique({ where: { slug } });
  if (existing) throw new Error(`Slug "${slug}" is already in use`);

  const row = await prisma.journalPost.create({
    data: { slug, title: input.title, excerpt: input.excerpt, body: input.body, status: "draft" },
  });
  return { id: row.id };
}

export async function updateJournalPost(id: string, input: Partial<JournalPostInput>): Promise<void> {
  await prisma.journalPost.update({
    where: { id },
    data: { title: input.title, excerpt: input.excerpt, body: input.body },
  });
}

export async function publishJournalPost(id: string): Promise<void> {
  const row = await prisma.journalPost.findUniqueOrThrow({ where: { id } });
  if (!row.title.trim() || !row.excerpt.trim() || !row.body.trim()) {
    throw new Error("Needs a title, excerpt, and body before publishing");
  }
  await prisma.journalPost.update({
    where: { id },
    data: { status: "published", publishedAt: row.publishedAt ?? new Date() },
  });
}

export async function unpublishJournalPost(id: string): Promise<void> {
  await prisma.journalPost.update({ where: { id }, data: { status: "draft" } });
}

export async function archiveJournalPost(id: string): Promise<void> {
  await prisma.journalPost.update({ where: { id }, data: { status: "archived" } });
}
