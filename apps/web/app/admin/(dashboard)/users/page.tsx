import { listUsersForAdmin } from "@/lib/admin/usersReader";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium" }).format(d);
}

export const dynamic = "force-dynamic";

export default async function AdminUsersPage() {
  const users = await listUsersForAdmin(100);

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Users</h1>
      <p className="mb-6 text-[13px] text-[var(--inner-ink-soft)]">
        Minimal identity fields only — assessment answers and report content are never shown here.
      </p>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Email</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Created</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Assessments completed</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Purchases</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Marketing consent</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Last activity</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="px-4 py-3 font-medium text-[var(--inner-ink)]">{u.email}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(u.createdAt)}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{u.assessmentsCompleted}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">{u.purchases}</td>
                <td className="px-4 py-3 text-[var(--inner-ink-soft)]">
                  {u.marketingConsent === null ? "—" : u.marketingConsent ? "Opted in" : "Declined"}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                  {u.lastActivity ? formatDate(u.lastActivity) : "—"}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No users yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
