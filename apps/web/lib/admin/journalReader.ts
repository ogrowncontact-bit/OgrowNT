import { prisma } from "@inner/db";
import type { JournalPost } from "@inner/db";

export async function listJournalPostsForAdmin(): Promise<JournalPost[]> {
  return prisma.journalPost.findMany({ orderBy: { updatedAt: "desc" } });
}

export async function getJournalPostById(id: string): Promise<JournalPost | null> {
  return prisma.journalPost.findUnique({ where: { id } });
}
