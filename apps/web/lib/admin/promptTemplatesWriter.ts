import { prisma, type PromptTemplateStatus } from "@inner/db";

export interface PromptTemplateInput {
  personaName: string;
  personaFocus: string;
  personaPrompt: string;
  toneWarmth: number;
  toneDirectness: number;
  toneDepth: number;
  toneFormality: number;
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

async function nextVersion(assessmentSlug: string): Promise<number> {
  const latest = await prisma.promptTemplate.findFirst({ where: { assessmentSlug }, orderBy: { version: "desc" } });
  return (latest?.version ?? 0) + 1;
}

/** New draft for an assessment that has no PromptTemplate at all yet. */
export async function createPromptTemplate(assessmentSlug: string, input: PromptTemplateInput, adminId: string) {
  const version = await nextVersion(assessmentSlug);
  return prisma.promptTemplate.create({
    data: {
      assessmentSlug,
      version,
      status: "draft",
      personaName: input.personaName,
      personaFocus: input.personaFocus,
      personaPrompt: input.personaPrompt,
      toneWarmth: clamp01(input.toneWarmth),
      toneDirectness: clamp01(input.toneDirectness),
      toneDepth: clamp01(input.toneDepth),
      toneFormality: clamp01(input.toneFormality),
      createdByAdminId: adminId,
    },
  });
}

/** Copies an existing row (any status, including published/archived) into a brand-new draft version — the only way to change a published prompt's content, since publishing never mutates a row in place. */
export async function duplicatePromptTemplate(sourceId: string, adminId: string) {
  const source = await prisma.promptTemplate.findUniqueOrThrow({ where: { id: sourceId } });
  const version = await nextVersion(source.assessmentSlug);
  return prisma.promptTemplate.create({
    data: {
      assessmentSlug: source.assessmentSlug,
      version,
      status: "draft",
      personaName: source.personaName,
      personaFocus: source.personaFocus,
      personaPrompt: source.personaPrompt,
      toneWarmth: source.toneWarmth,
      toneDirectness: source.toneDirectness,
      toneDepth: source.toneDepth,
      toneFormality: source.toneFormality,
      createdByAdminId: adminId,
    },
  });
}

/** Only a draft or testing row can be edited in place — a published or archived row is immutable history; duplicate it to make changes instead. */
export async function updatePromptTemplate(id: string, input: PromptTemplateInput): Promise<{ ok: true } | { ok: false; error: string }> {
  const existing = await prisma.promptTemplate.findUniqueOrThrow({ where: { id } });
  if (existing.status === "published" || existing.status === "archived") {
    return { ok: false, error: `Cannot edit a ${existing.status} prompt — duplicate it to create an editable draft.` };
  }
  await prisma.promptTemplate.update({
    where: { id },
    data: {
      personaName: input.personaName,
      personaFocus: input.personaFocus,
      personaPrompt: input.personaPrompt,
      toneWarmth: clamp01(input.toneWarmth),
      toneDirectness: clamp01(input.toneDirectness),
      toneDepth: clamp01(input.toneDepth),
      toneFormality: clamp01(input.toneFormality),
    },
  });
  return { ok: true };
}

/** Moves a row to `testing` — a step between draft and published for admin's own manual QA via the playground. Any status can move to testing except archived. */
export async function markPromptTemplateTesting(id: string): Promise<{ ok: true } | { ok: false; error: string }> {
  const existing = await prisma.promptTemplate.findUniqueOrThrow({ where: { id } });
  if (existing.status === "archived") return { ok: false, error: "Cannot move an archived prompt to testing — duplicate it first." };
  await prisma.promptTemplate.update({ where: { id }, data: { status: "testing" } });
  return { ok: true };
}

/**
 * Publishing never mutates a prompt's content — it only flips status and
 * demotes whichever OTHER row for the same assessment was previously
 * published (there is never more than one live published row per
 * assessment at a time — apps/web/lib/promptTemplates.ts's
 * getPublishedPersona() relies on that).
 */
export async function publishPromptTemplate(id: string): Promise<{ ok: true } | { ok: false; error: string }> {
  const target = await prisma.promptTemplate.findUniqueOrThrow({ where: { id } });
  if (target.status === "published") return { ok: true }; // already live, nothing to do
  if (target.status === "archived") return { ok: false, error: "Cannot publish an archived prompt — duplicate it first." };
  if (!target.personaPrompt.trim()) return { ok: false, error: "personaPrompt is empty — nothing to publish." };

  const currentlyPublished = await prisma.promptTemplate.findFirst({
    where: { assessmentSlug: target.assessmentSlug, status: "published", NOT: { id: target.id } },
  });

  await prisma.$transaction([
    ...(currentlyPublished ? [prisma.promptTemplate.update({ where: { id: currentlyPublished.id }, data: { status: "archived" as PromptTemplateStatus } })] : []),
    prisma.promptTemplate.update({ where: { id: target.id }, data: { status: "published", publishedAt: new Date() } }),
  ]);
  return { ok: true };
}

export async function archivePromptTemplate(id: string): Promise<{ ok: true } | { ok: false; error: string }> {
  const target = await prisma.promptTemplate.findUniqueOrThrow({ where: { id } });
  if (target.status === "published") {
    return { ok: false, error: "Cannot archive the currently published prompt directly — publish a replacement first, which archives this one automatically." };
  }
  await prisma.promptTemplate.update({ where: { id }, data: { status: "archived" } });
  return { ok: true };
}
