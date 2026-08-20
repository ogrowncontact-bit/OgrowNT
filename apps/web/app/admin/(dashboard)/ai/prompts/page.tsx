import Link from "next/link";
import { listPromptTemplates } from "@/lib/admin/promptTemplatesReader";

export const dynamic = "force-dynamic";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const STATUS_COLOR: Record<string, string> = {
  draft: "text-[var(--inner-muted)]",
  testing: "text-[var(--inner-accent-soft)]",
  published: "text-[var(--inner-accent)]",
  archived: "text-[var(--inner-muted)]",
};

export default async function AdminPromptsPage() {
  const rows = await listPromptTemplates();

  const byAssessment = new Map<string, typeof rows>();
  for (const row of rows) {
    const list = byAssessment.get(row.assessmentSlug) ?? [];
    list.push(row);
    byAssessment.set(row.assessmentSlug, list);
  }

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">AI Prompts</h1>
      <p className="mb-6 max-w-lg text-[13px] text-[var(--inner-ink-soft)]">
        Layer 2 of the Prompt Orchestration System — each assessment's own interpretive persona and voice. The
        brand-level safety rules (Layer 1) are not shown here and can't be edited from this screen; only the
        assessment-specific persona and tone can be changed, versioned, and published.
      </p>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="px-4 py-3 font-medium">Assessment</th>
              <th className="px-4 py-3 font-medium">Persona</th>
              <th className="px-4 py-3 font-medium">Version</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Updated</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No prompt templates yet — run `pnpm --filter @inner/db seed:prompts`.
                </td>
              </tr>
            )}
            {[...byAssessment.entries()].map(([slug, versions]) =>
              versions.map((row, i) => (
                <tr key={row.id} className="border-b border-[var(--inner-line)] last:border-0">
                  <td className="px-4 py-3 text-[var(--inner-ink)]">{i === 0 ? row.assessmentName : ""}</td>
                  <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{row.personaName}</td>
                  <td className="px-4 py-3 text-[var(--inner-muted)]">v{row.version}</td>
                  <td className={`px-4 py-3 font-medium ${STATUS_COLOR[row.status] ?? ""}`}>{row.status}</td>
                  <td className="px-4 py-3 text-[var(--inner-muted)]">{formatDate(row.updatedAt)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/admin/ai/prompts/${row.id}`} className="text-[var(--inner-accent)] underline underline-offset-2">
                      Open
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
