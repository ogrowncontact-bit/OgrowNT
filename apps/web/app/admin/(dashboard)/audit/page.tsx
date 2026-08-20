import { listAuditLog } from "@/lib/admin/auditLogReader";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

function formatAction(action: string): string {
  return action
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export const dynamic = "force-dynamic";

export default async function AdminAuditPage() {
  const rows = await listAuditLog();

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Audit Log</h1>
      <p className="mb-6 text-[13px] text-[var(--inner-ink-soft)]">
        Every admin mutation, most recent first. Who, what, when, and which resource — {rows.length} most recent entries.
      </p>

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">When</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Who</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Action</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Resource</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{formatDate(r.createdAt)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{r.adminEmail}</td>
                <td className="whitespace-nowrap px-4 py-3 font-medium text-[var(--inner-ink)]">{formatAction(r.action)}</td>
                <td className="px-4 py-3 text-[var(--inner-muted)]">
                  {r.entityType} · {r.entityId.slice(0, 12)}…
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No admin actions recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
