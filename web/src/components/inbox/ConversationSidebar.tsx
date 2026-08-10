"use client";

import { useEffect, useState } from "react";
import { addNote, assignConversation, listMembers } from "@/lib/inbox";
import type { ConversationDetail, TeamMember } from "@/lib/types";

// Coluna direita: dados do cliente, atribuicao a um membro da equipe, e
// notas internas (nunca enviadas ao cliente - ver ConversationNote no
// schema). Recebe `detail` do pai (InboxView) pelo mesmo motivo do
// ConversationThread: evitar polling duplicado do mesmo endpoint.
export function ConversationSidebar({
  businessId,
  token,
  detail,
  onMutated,
}: {
  businessId: string;
  token: string;
  detail: ConversationDetail;
  onMutated: () => void;
}) {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [noteText, setNoteText] = useState("");
  const [savingNote, setSavingNote] = useState(false);

  useEffect(() => {
    listMembers(businessId, token).then(setMembers).catch(() => {});
  }, [businessId, token]);

  async function handleAssign(e: React.ChangeEvent<HTMLSelectElement>) {
    const userId = e.target.value || null;
    await assignConversation(businessId, token, detail.id, userId);
    onMutated();
  }

  async function handleAddNote(e: React.FormEvent) {
    e.preventDefault();
    if (!noteText.trim()) return;
    setSavingNote(true);
    try {
      await addNote(businessId, token, detail.id, noteText.trim());
      setNoteText("");
      onMutated();
    } finally {
      setSavingNote(false);
    }
  }

  return (
    <div className="flex h-full w-72 shrink-0 flex-col border-l border-zinc-200 dark:border-zinc-800">
      <div className="border-b border-zinc-200 p-4 dark:border-zinc-800">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">Cliente</h3>
        <p className="text-sm text-zinc-900 dark:text-zinc-100">{detail.customer.name || "Sem nome"}</p>
        <p className="text-xs text-zinc-400">{detail.customer.phoneNumber}</p>
        <p className="mt-1 text-xs text-zinc-400">Idioma: {detail.customer.preferredLanguage}</p>
      </div>

      <div className="border-b border-zinc-200 p-4 dark:border-zinc-800">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">Atribuido a</h3>
        <select
          value={detail.assignedToUserId ?? ""}
          onChange={handleAssign}
          className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">Ninguem</option>
          {members.map((m) => (
            <option key={m.userId} value={m.userId}>
              {m.name} ({m.role})
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden p-4">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">Notas internas</h3>
        <div className="flex-1 space-y-2 overflow-y-auto">
          {detail.notes.length === 0 && <p className="text-xs text-zinc-400">Nenhuma nota ainda.</p>}
          {detail.notes.map((n) => (
            <div key={n.id} className="rounded-md bg-zinc-50 p-2 text-xs dark:bg-zinc-900">
              <p className="text-zinc-700 dark:text-zinc-300">{n.content}</p>
              <p className="mt-1 text-[10px] text-zinc-400">
                {n.user.name} - {new Date(n.createdAt).toLocaleString("pt-PT")}
              </p>
            </div>
          ))}
        </div>
        <form onSubmit={handleAddNote} className="mt-2 flex gap-1">
          <input
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="Adicionar nota..."
            className="flex-1 rounded-md border border-zinc-300 px-2 py-1.5 text-xs outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button
            type="submit"
            disabled={savingNote || !noteText.trim()}
            className="rounded-md bg-zinc-900 px-2.5 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900"
          >
            Salvar
          </button>
        </form>
      </div>
    </div>
  );
}
