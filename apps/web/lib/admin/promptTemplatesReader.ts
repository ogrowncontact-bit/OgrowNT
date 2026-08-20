import { prisma } from "@inner/db";
import { allAssessments } from "@inner/content";

export interface PromptTemplateRow {
  id: string;
  assessmentSlug: string;
  assessmentName: string;
  version: number;
  status: "draft" | "testing" | "published" | "archived";
  personaName: string;
  updatedAt: Date;
}

const assessmentNameBySlug = Object.fromEntries(allAssessments.map((a) => [a.slug, a.name]));

/** Every PromptTemplate row across every assessment, newest first — the /admin/ai/prompts list. */
export async function listPromptTemplates(): Promise<PromptTemplateRow[]> {
  const rows = await prisma.promptTemplate.findMany({ orderBy: [{ assessmentSlug: "asc" }, { version: "desc" }] });
  return rows.map((r) => ({
    id: r.id,
    assessmentSlug: r.assessmentSlug,
    assessmentName: assessmentNameBySlug[r.assessmentSlug] ?? r.assessmentSlug,
    version: r.version,
    status: r.status,
    personaName: r.personaName,
    updatedAt: r.updatedAt,
  }));
}

export async function getPromptTemplateById(id: string) {
  return prisma.promptTemplate.findUnique({ where: { id } });
}
