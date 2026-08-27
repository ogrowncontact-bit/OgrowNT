import type { AuditLogEntry } from "@/lib/api";

// Audit Center — "PROMPT 14" §94-95. Read-only by design: this component
// has no mutation of its own (nothing in this dashboard can ever UPDATE or
// DELETE an AuditLog row — apps/api/routers/audit.py exposes GET only),
// matching §95's "auditoria não deve ser facilmente alterável pelos agentes."
export function AuditLogViewer({ entries }: { entries: AuditLogEntry[] }) {
  return (
    <section className="mb-6 rounded-lg border border-base-700 bg-base-900 p-4">
      <p className="mb-3 text-[11px] uppercase tracking-wider text-ink-500">
        Audit Center {entries.length ? `(${entries.length})` : ""}
      </p>
      <p className="mb-3 text-[10px] text-ink-500">
        Immutable — nothing in this dashboard, or the API behind it, can edit or delete an audit entry.
      </p>
      {entries.length === 0 ? (
        <p className="text-xs text-ink-500">No audited actions recorded yet.</p>
      ) : (
        <div className="max-h-[32rem] overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wide text-ink-500">
                <th className="pb-2 pr-3 font-normal">When</th>
                <th className="pb-2 pr-3 font-normal">Actor</th>
                <th className="pb-2 pr-3 font-normal">Action</th>
                <th className="pb-2 font-normal">Entity</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-t border-base-700/60">
                  <td className="py-1.5 pr-3 text-ink-500">{new Date(e.ts).toLocaleString()}</td>
                  <td className="py-1.5 pr-3 text-ink-300">{e.actor}</td>
                  <td className="py-1.5 pr-3 text-ink-100">{e.action}</td>
                  <td className="py-1.5 text-ink-500">
                    {e.entity_type ? `${e.entity_type}${e.entity_id != null ? `#${e.entity_id}` : ""}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
