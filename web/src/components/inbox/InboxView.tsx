"use client";

import { useCallback, useEffect, useState } from "react";
import { getConversation } from "@/lib/inbox";
import type { ConversationDetail } from "@/lib/types";
import { ConversationList } from "./ConversationList";
import { ConversationSidebar } from "./ConversationSidebar";
import { ConversationThread } from "./ConversationThread";

const POLL_MS = 4000;

// Orquestra as 3 colunas do Inbox para uma empresa. O detalhe da conversa
// selecionada e buscado uma vez aqui (com polling) e passado para a thread e
// a barra lateral, para as duas nunca pedirem o mesmo endpoint em paralelo.
export function InboxView({ businessId, token }: { businessId: string; token: string }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);

  const refetchDetail = useCallback(async () => {
    if (!selectedId) return;
    const data = await getConversation(businessId, token, selectedId);
    setDetail(data);
  }, [businessId, token, selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    async function load() {
      const data = await getConversation(businessId, token, selectedId as string);
      if (!cancelled) setDetail(data);
    }
    load();
    const interval = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [businessId, token, selectedId]);

  // Enquanto o detalhe da nova conversa ainda nao chegou, nao mostra o
  // detalhe da conversa anterior (evita um "flash" de dados trocados).
  const activeDetail = detail && detail.id === selectedId ? detail : null;

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="w-80 shrink-0">
        <ConversationList businessId={businessId} token={token} selectedId={selectedId} onSelect={setSelectedId} />
      </div>

      {activeDetail ? (
        <>
          <ConversationThread businessId={businessId} token={token} detail={activeDetail} onMutated={refetchDetail} />
          <ConversationSidebar businessId={businessId} token={token} detail={activeDetail} onMutated={refetchDetail} />
        </>
      ) : (
        <div className="flex flex-1 items-center justify-center text-sm text-zinc-400">
          Selecione uma conversa para comecar.
        </div>
      )}
    </div>
  );
}
