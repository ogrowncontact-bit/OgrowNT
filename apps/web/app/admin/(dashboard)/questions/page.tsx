import Link from "next/link";
import { listAssessmentsForAdmin } from "@/lib/admin/catalogReader";

export const dynamic = "force-dynamic";

export default async function AdminQuestionsIndexPage() {
  const assessments = await listAssessmentsForAdmin();

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Questions</h1>
      <p className="mb-6 text-[13px] text-[var(--inner-ink-soft)]">
        Questions are edited per-discovery — core questions and the adaptive pool, with dimension mapping, weight,
        sensitivity, and adaptive follow-up candidates. Pick a discovery to open its question editor.
      </p>
      <div className="space-y-3">
        {assessments.map((a) => (
          <Link
            key={a.id}
            href={`/admin/assessments/${a.id}`}
            className="block rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4 hover:border-[var(--inner-accent-soft)]"
          >
            <p className="font-medium text-[var(--inner-ink)]">{a.name}</p>
            <p className="text-[13px] text-[var(--inner-ink-soft)]">/{a.slug} · {a.status}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
