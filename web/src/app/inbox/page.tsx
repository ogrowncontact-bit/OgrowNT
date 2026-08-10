"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { InboxView } from "@/components/inbox/InboxView";
import { useAuth } from "@/context/AuthContext";

export default function InboxPage() {
  const { token, user, memberships, loading, logout } = useAuth();
  const router = useRouter();
  const [selectedBusinessId, setSelectedBusinessId] = useState<string | null>(null);
  // Deriva a empresa ativa em vez de sincronizar via effect: se o usuario
  // ainda nao escolheu explicitamente (selectedBusinessId nulo), usa a
  // primeira empresa da lista.
  const businessId = selectedBusinessId ?? memberships[0]?.business.id ?? null;

  useEffect(() => {
    if (!loading && !token) router.replace("/login");
  }, [loading, token, router]);

  if (loading || !token || !user) {
    return <div className="flex flex-1 items-center justify-center text-sm text-zinc-400">Carregando...</div>;
  }

  if (memberships.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-zinc-400">
        Sua conta ainda nao esta vinculada a nenhuma empresa.
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-2.5 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">AI Front Desk - Inbox</span>
          {memberships.length > 1 ? (
            <select
              value={businessId ?? ""}
              onChange={(e) => setSelectedBusinessId(e.target.value)}
              className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              {memberships.map((m) => (
                <option key={m.business.id} value={m.business.id}>
                  {m.business.name}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-sm text-zinc-500">{memberships[0].business.name}</span>
          )}
        </div>
        <div className="flex items-center gap-3 text-sm text-zinc-500">
          <span>{user.name}</span>
          <button onClick={logout} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200">
            Sair
          </button>
        </div>
      </header>
      {businessId && <InboxView key={businessId} businessId={businessId} token={token} />}
    </div>
  );
}
