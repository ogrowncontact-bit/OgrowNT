import Link from "next/link";
import { listJournalPostsForAdmin } from "@/lib/admin/journalReader";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium" }).format(d);
}

export const dynamic = "force-dynamic";

export default async function AdminJournalPage() {
  const posts = await listJournalPostsForAdmin();

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-[24px] text-[var(--inner-ink)]">Journal</h1>
        <Link
          href="/admin/journal/new"
          className="rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-4 py-2 text-[14px] font-medium text-[var(--inner-accent-contrast)]"
        >
          + New post
        </Link>
      </div>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[14px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Title</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Status</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody>
            {posts.map((p) => (
              <tr key={p.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3">
                  <Link href={`/admin/journal/${p.id}`} className="font-medium text-[var(--inner-ink)] hover:underline">
                    {p.title || "Untitled"}
                  </Link>
                  <span className="ml-2 text-[var(--inner-muted)]">/{p.slug}</span>
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  <span
                    className={
                      p.status === "published"
                        ? "text-[var(--inner-accent)]"
                        : p.status === "archived"
                          ? "text-[var(--inner-muted)]"
                          : "text-[var(--inner-ink-soft)]"
                    }
                  >
                    {p.status}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(p.updatedAt)}</td>
              </tr>
            ))}
            {posts.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No journal posts yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
