"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { handoffConversation, resolveConversation, sendHumanReply } from "@/lib/inbox";
import type { ConversationDetail } from "@/lib/types";

function senderLabel(sender: ConversationDetail["messages"][number]["sender"]): string {
  switch (sender) {
    case "CUSTOMER":
      return "Cliente";
    case "AGENT":
      return "Bot";
    case "HUMAN":
      return "Atendente";
    case "SYSTEM":
      return "Sistema";
  }
}

// Coluna central: historico da conversa + resposta manual do atendente.
// Recebe `detail` ja carregado pelo pai (InboxView, que faz o polling) para
// nao duplicar chamadas - so aciona `onMutated` apos uma acao que muda o
// estado no servidor, para o pai buscar a versao atualizada.
export function ConversationThread({
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
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [detail.messages.length]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    setError(null);
    try {
      await sendHumanReply(businessId, token, detail.id, text.trim());
      setText("");
      onMutated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel enviar a mensagem.");
    } finally {
      setSending(false);
    }
  }

  async function handleHandoff() {
    await handoffConversation(businessId, token, detail.id);
    onMutated();
  }

  async function handleResolve() {
    await resolveConversation(businessId, token, detail.id);
    onMutated();
  }

  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div>
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
            {detail.customer.name || detail.customer.phoneNumber}
          </p>
          <p className="text-xs text-zinc-400">{detail.customer.phoneNumber}</p>
        </div>
        {detail.needsHuman ? (
          <button
            onClick={handleResolve}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
          >
            Devolver ao bot
          </button>
        ) : (
          <button
            onClick={handleHandoff}
            className="rounded-md bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-500"
          >
            Assumir conversa (pausar bot)
          </button>
        )}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {detail.messages.map((m) => {
          const fromCustomer = m.sender === "CUSTOMER";
          return (
            <div key={m.id} className={`flex flex-col ${fromCustomer ? "items-start" : "items-end"}`}>
              <span className="mb-0.5 text-[10px] uppercase tracking-wide text-zinc-400">{senderLabel(m.sender)}</span>
              <div
                className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                  fromCustomer
                    ? "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                    : m.sender === "HUMAN"
                      ? "bg-blue-600 text-white"
                      : "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                }`}
              >
                {m.content}
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="flex items-end gap-2 border-t border-zinc-200 p-3 dark:border-zinc-800">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend(e);
            }
          }}
          rows={2}
          placeholder="Responder como atendente..."
          className="flex-1 resize-none rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button
          type="submit"
          disabled={sending || !text.trim()}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900"
        >
          Enviar
        </button>
      </form>
      {error && <p className="px-3 pb-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}
