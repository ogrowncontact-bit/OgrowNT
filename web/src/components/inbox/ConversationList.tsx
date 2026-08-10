"use client";

import { useEffect, useState } from "react";
import { listConversations } from "@/lib/inbox";
import type { ConversationListItem } from "@/lib/types";

const POLL_MS = 6000;

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "agora";
  if (minutes < 60) return `${minutes}min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

export function ConversationList({
  businessId,
  token,
  selectedId,
  onSelect,
}: {
  businessId: string;
  token: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [onlyNeedsHuman, setOnlyNeedsHuman] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let isFirstLoad = true;
    async function load() {
      if (isFirstLoad) {
        setLoading(true);
        isFirstLoad = false;
      }
      try {
        const data = await listConversations(businessId, token, onlyNeedsHuman ? true : undefined);
        if (!cancelled) setConversations(data);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [businessId, token, onlyNeedsHuman]);

  return (
    <div className="flex h-full flex-col border-r border-zinc-200 dark:border-zinc-800">
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Conversas</h2>
        <button
          onClick={() => setOnlyNeedsHuman((v) => !v)}
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            onlyNeedsHuman
              ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
          }`}
        >
          {onlyNeedsHuman ? "Precisam de atendimento" : "Todas"}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading && conversations.length === 0 && (
          <p className="p-4 text-sm text-zinc-400">Carregando...</p>
        )}
        {!loading && conversations.length === 0 && (
          <p className="p-4 text-sm text-zinc-400">Nenhuma conversa por aqui.</p>
        )}
        {conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => onSelect(c.id)}
            className={`block w-full border-b border-zinc-100 px-4 py-3 text-left transition-colors dark:border-zinc-900 ${
              selectedId === c.id ? "bg-zinc-100 dark:bg-zinc-900" : "hover:bg-zinc-50 dark:hover:bg-zinc-900/50"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
                {c.customer.name || c.customer.phoneNumber}
              </span>
              <span className="shrink-0 text-xs text-zinc-400">{timeAgo(c.lastMessageAt)}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              {c.needsHuman && (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                  precisa de humano
                </span>
              )}
              <span className="text-[10px] uppercase tracking-wide text-zinc-400">{c.channel}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
