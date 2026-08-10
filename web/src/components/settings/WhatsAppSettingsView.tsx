"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { connectWhatsApp, getWhatsAppConnection } from "@/lib/whatsapp";
import type { WhatsAppConnection } from "@/lib/types";

export function WhatsAppSettingsView({ businessId, token }: { businessId: string; token: string }) {
  const [connection, setConnection] = useState<WhatsAppConnection | null>(null);
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [wabaId, setWabaId] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [verifiedName, setVerifiedName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const conn = await getWhatsAppConnection(businessId, token);
        if (!cancelled) setConnection(conn);
      } catch {
        if (!cancelled) setError("Nao foi possivel carregar o status da conexao com o WhatsApp.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [businessId, token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const conn = await connectWhatsApp(businessId, token, {
        phoneNumberId: phoneNumberId.trim(),
        wabaId: wabaId.trim(),
        accessToken: accessToken.trim(),
        verifiedName: verifiedName.trim() || undefined,
      });
      setConnection(conn);
      setAccessToken("");
      setSuccess("WhatsApp conectado com sucesso.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel conectar o WhatsApp.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h1 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-50">Conectar WhatsApp</h1>

      {connection?.connected ? (
        <div className="mb-6 max-w-xl rounded-lg border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-900/20">
          <p className="text-sm font-medium text-emerald-800 dark:text-emerald-300">
            Conectado{connection.verifiedName ? ` como ${connection.verifiedName}` : ""}
          </p>
          <p className="mt-1 text-xs text-emerald-700 dark:text-emerald-400">
            Numero (phone_number_id): {connection.phoneNumberId}
          </p>
          <p className="text-xs text-emerald-700 dark:text-emerald-400">
            Conectado em {new Date(connection.connectedAt).toLocaleString("pt-BR")}
          </p>
        </div>
      ) : (
        connection && (
          <p className="mb-4 max-w-xl text-sm text-zinc-500">
            Nenhum numero de WhatsApp conectado ainda. Enquanto isso, o bot roda em modo de teste (as mensagens
            aparecem so nos logs do servidor, nao chegam a um WhatsApp de verdade).
          </p>
        )
      )}

      <form onSubmit={handleSubmit} className="max-w-xl space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <p className="text-xs text-zinc-500">
          Pegue esses valores no Meta Business Manager, no app do WhatsApp Business (produto &quot;WhatsApp&quot;
          dentro do seu app em developers.facebook.com).
        </p>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Phone number ID</label>
          <input
            required
            value={phoneNumberId}
            onChange={(e) => setPhoneNumberId(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            WhatsApp Business Account ID (WABA ID)
          </label>
          <input
            required
            value={wabaId}
            onChange={(e) => setWabaId(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Token de acesso permanente
          </label>
          <input
            required
            type="password"
            value={accessToken}
            onChange={(e) => setAccessToken(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          {connection?.connected && (
            <p className="mt-1 text-xs text-zinc-400">
              Por segurança o token nunca é mostrado de volta — pra atualizar a conexão, cole o token novamente.
            </p>
          )}
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Nome verificado (opcional)
          </label>
          <input
            value={verifiedName}
            onChange={(e) => setVerifiedName(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {success && <p className="text-sm text-emerald-600">{success}</p>}

        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900"
        >
          {connection?.connected ? "Atualizar conexao" : "Conectar WhatsApp"}
        </button>
      </form>
    </div>
  );
}
