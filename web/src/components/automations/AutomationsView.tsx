"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { createAutomation, deleteAutomation, listAutomations, updateAutomation } from "@/lib/automations";
import type { Automation, AutomationTrigger } from "@/lib/types";

const TRIGGER_LABELS: Record<AutomationTrigger, string> = {
  BOOKING_REMINDER: "Lembrete (antes do agendamento)",
  BOOKING_FOLLOWUP: "Follow-up (depois do agendamento)",
};

function formatOffset(trigger: AutomationTrigger, minutes: number): string {
  const unit = minutes % 1440 === 0 ? `${minutes / 1440} dia(s)` : minutes % 60 === 0 ? `${minutes / 60}h` : `${minutes}min`;
  return trigger === "BOOKING_REMINDER" ? `${unit} antes` : `${unit} depois`;
}

export function AutomationsView({ businessId, token }: { businessId: string; token: string }) {
  const [automations, setAutomations] = useState<Automation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newTrigger, setNewTrigger] = useState<AutomationTrigger>("BOOKING_REMINDER");
  const [newOffsetHours, setNewOffsetHours] = useState(24);
  const [saving, setSaving] = useState(false);

  async function refresh() {
    const data = await listAutomations(businessId, token);
    setAutomations(data);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await listAutomations(businessId, token);
        if (!cancelled) setAutomations(data);
      } catch {
        if (!cancelled) setError("Nao foi possivel carregar as automacoes.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [businessId, token]);

  async function handleToggle(automation: Automation) {
    setError(null);
    try {
      await updateAutomation(businessId, token, automation.id, { active: !automation.active });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel atualizar a automacao.");
    }
  }

  async function handleDelete(automation: Automation) {
    setError(null);
    try {
      await deleteAutomation(businessId, token, automation.id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel remover a automacao.");
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await createAutomation(businessId, token, { trigger: newTrigger, offsetMinutes: Math.round(newOffsetHours * 60) });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel criar a automacao.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mb-2">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Automacoes</h1>
        <p className="mt-1 max-w-2xl text-xs text-zinc-400">
          Lembretes e follow-ups automaticos por WhatsApp. O texto vem de um template ja aprovado no Meta Business Manager
          (o WhatsApp nao permite texto livre fora da janela de 24h de conversa) - aqui voce so liga/desliga e ajusta quando
          cada um dispara.
        </p>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {!automations && !error && <p className="mt-4 text-sm text-zinc-400">Carregando...</p>}

      {automations && (
        <div className="mt-4 max-w-2xl overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
          {automations.length === 0 ? (
            <p className="p-4 text-sm text-zinc-400">Nenhuma automacao configurada.</p>
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
              {automations.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-3 bg-white p-4 dark:bg-zinc-950">
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{TRIGGER_LABELS[a.trigger]}</p>
                    <p className="text-xs text-zinc-400">{formatOffset(a.trigger, a.offsetMinutes)}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => handleToggle(a)}
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        a.active
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                          : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                      }`}
                    >
                      {a.active ? "Ativa" : "Desativada"}
                    </button>
                    <button onClick={() => handleDelete(a)} className="text-xs text-zinc-400 hover:text-red-600">
                      Remover
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <form onSubmit={handleCreate} className="mt-6 flex max-w-2xl flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-500">Tipo</label>
          <select
            value={newTrigger}
            onChange={(e) => setNewTrigger(e.target.value as AutomationTrigger)}
            className="rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="BOOKING_REMINDER">Lembrete</option>
            <option value="BOOKING_FOLLOWUP">Follow-up</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-500">
            {newTrigger === "BOOKING_REMINDER" ? "Horas antes" : "Horas depois"}
          </label>
          <input
            type="number"
            min={0}
            step={0.5}
            value={newOffsetHours}
            onChange={(e) => setNewOffsetHours(Number(e.target.value))}
            className="w-28 rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>
        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900"
        >
          Adicionar
        </button>
      </form>
    </div>
  );
}
