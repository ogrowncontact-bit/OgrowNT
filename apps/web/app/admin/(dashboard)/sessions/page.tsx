import { getSessionStatusCounts, listSessionsForAdmin } from "@/lib/admin/sessionsReader";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const cardLabel = "text-[12px] text-[var(--inner-muted)]";
const cardValue = "font-display text-[22px] text-[var(--inner-ink)]";

const STATUS_LABEL: Record<string, string> = {
  in_progress: "In progress",
  completed: "Completed",
  abandoned: "Abandoned",
};

export const dynamic = "force-dynamic";

/**
 * FASE 29 §ADMIN — "inspect assessment sessions, completion, profile
 * result, AI status, quality gate — without unnecessarily exposing
 * sensitive raw answers." Never queries Response/OpenResponse content;
 * lib/admin/sessionsReader.ts only ever reads counts, status, and the
 * already-decided profile name.
 */
export default async function AdminSessionsPage() {
  const [counts, sessions] = await Promise.all([getSessionStatusCounts(), listSessionsForAdmin(150)]);

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Assessment Sessions</h1>
      <p className="mb-6 max-w-2xl text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">
        Every session across the funnel — started, completed, or abandoned — with the profile it resolved to and
        whether AI ran for it. Raw answers are never shown here or anywhere in admin.
      </p>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className={cardLabel}>In progress</p>
          <p className={cardValue}>{counts.inProgress}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Completed</p>
          <p className={cardValue}>{counts.completed}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Abandoned</p>
          <p className={cardValue}>{counts.abandoned}</p>
        </div>
        <div className={card}>
          <p className={cardLabel}>Purchased</p>
          <p className={cardValue}>{counts.purchased}</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Started</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Experience</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Status</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Questions</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Profile result</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">AI status</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Purchased</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(s.startedAt)}</td>
                <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">/{s.assessmentSlug}</td>
                <td className="px-4 py-3">
                  <span className={s.status === "abandoned" ? "text-[var(--inner-accent)]" : "text-[var(--inner-ink-soft)]"}>
                    {STATUS_LABEL[s.status] ?? s.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{s.questionCount}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{s.primaryProfileName ?? "—"}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">
                  {s.status === "completed" ? (s.aiGenerated ? "AI-generated" : "Static fallback") : "—"}
                </td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{s.purchased ? "Yes" : "—"}</td>
              </tr>
            ))}
            {sessions.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No sessions yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
