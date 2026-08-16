import Link from "next/link";
import { listAssessmentsForAdmin } from "@/lib/admin/catalogReader";

export default async function AdminAssessmentsPage() {
  const assessments = await listAssessmentsForAdmin();

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-[24px] text-[var(--inner-ink)]">Assessments</h1>
        <Link
          href="/admin/assessments/new"
          className="rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-4 py-2 text-[14px] font-medium text-[var(--inner-accent-contrast)]"
        >
          + New experience
        </Link>
      </div>

      <div className="overflow-hidden rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[14px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Slug</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Version</th>
            </tr>
          </thead>
          <tbody>
            {assessments.map((a) => (
              <tr key={a.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="px-4 py-3">
                  <Link href={`/admin/assessments/${a.id}`} className="font-medium text-[var(--inner-ink)] hover:underline">
                    {a.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">/{a.slug}</td>
                <td className="px-4 py-3">
                  <span
                    className={
                      a.status === "published"
                        ? "text-[var(--inner-accent)]"
                        : a.status === "archived"
                          ? "text-[var(--inner-muted)]"
                          : "text-[var(--inner-ink-soft)]"
                    }
                  >
                    {a.status}
                    {a.hasDraft && a.status === "published" ? " (unpublished draft)" : ""}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{a.publishedVersion ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
