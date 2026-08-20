/**
 * Seeds just the default assessment personas (PromptTemplate rows) —
 * standalone from seed.ts's full catalog seed, which always CREATEs a new
 * AssessmentVersion and fails on a database that already has one (by
 * design — see seed.ts's own docstring: it's meant for a fresh dev DB).
 * This script is safe to run against an existing environment that already
 * has assessments seeded but predates the Prompt Orchestration System.
 */
import { PrismaClient } from "@prisma/client";
import { DEFAULT_ASSESSMENT_PERSONAS } from "@inner/ai";

const prisma = new PrismaClient();

async function main() {
  let created = 0;
  for (const persona of DEFAULT_ASSESSMENT_PERSONAS) {
    const existing = await prisma.promptTemplate.findFirst({ where: { assessmentSlug: persona.assessmentSlug } });
    if (existing) continue;
    await prisma.promptTemplate.create({
      data: {
        assessmentSlug: persona.assessmentSlug,
        version: 1,
        status: "published",
        personaName: persona.name,
        personaFocus: persona.focus,
        personaPrompt: persona.prompt,
        toneWarmth: persona.tone.warmth,
        toneDirectness: persona.tone.directness,
        toneDepth: persona.tone.depth,
        toneFormality: persona.tone.formality,
        publishedAt: new Date(),
      },
    });
    created++;
  }
  console.log(`Seeded ${created} new assessment persona(s); skipped ${DEFAULT_ASSESSMENT_PERSONAS.length - created} that already had one.`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
