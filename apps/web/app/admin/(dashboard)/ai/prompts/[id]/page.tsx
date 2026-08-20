import { notFound } from "next/navigation";
import Link from "next/link";
import { getAdminSession } from "@/lib/adminAuth";
import { getPromptTemplateById } from "@/lib/admin/promptTemplatesReader";
import { getAssessmentConfig } from "@/lib/assessments";
import { PromptEditor } from "@/components/admin/PromptEditor";

export const dynamic = "force-dynamic";

export default async function AdminPromptEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [session, template] = await Promise.all([getAdminSession(), getPromptTemplateById(id)]);
  if (!template) notFound();

  const config = await getAssessmentConfig(template.assessmentSlug);
  const profiles = config?.profiles.map((p) => ({ key: p.key, name: p.name })) ?? [];

  return (
    <div>
      <p className="mb-2 text-[12px] text-[var(--inner-muted)]">
        <Link href="/admin/ai/prompts" className="underline underline-offset-2">
          AI Prompts
        </Link>{" "}
        / {config?.name ?? template.assessmentSlug} / v{template.version}
      </p>
      <h1 className="font-display mb-6 text-[24px] text-[var(--inner-ink)]">
        {template.personaName} <span className="text-[16px] text-[var(--inner-muted)]">({template.status})</span>
      </h1>

      <PromptEditor
        template={{
          id: template.id,
          assessmentSlug: template.assessmentSlug,
          assessmentName: config?.name ?? template.assessmentSlug,
          version: template.version,
          status: template.status,
          personaName: template.personaName,
          personaFocus: template.personaFocus,
          personaPrompt: template.personaPrompt,
          toneWarmth: template.toneWarmth,
          toneDirectness: template.toneDirectness,
          toneDepth: template.toneDepth,
          toneFormality: template.toneFormality,
        }}
        profiles={profiles}
        readOnly={session?.role === "viewer"}
      />
    </div>
  );
}
