"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { getOnboarding, importFromWebsite, runQuickStart } from "@/lib/onboarding";
import { createService, listBusinessHours, listServices, saveBusinessHours, updateService } from "@/lib/services";
import type { BusinessHoursEntry, OnboardingStatus, Service, WebsiteImportSuggestion } from "@/lib/types";

const WEEKDAY_LABELS = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];

interface HourRow {
  weekday: number;
  open: boolean;
  openTime: string;
  closeTime: string;
}

interface DraftSuggestion extends WebsiteImportSuggestion {
  selected: boolean;
}

function buildHourRows(existing: BusinessHoursEntry[]): HourRow[] {
  return Array.from({ length: 7 }, (_, weekday) => {
    const found = existing.find((h) => h.weekday === weekday);
    return found
      ? { weekday, open: true, openTime: found.openTime, closeTime: found.closeTime }
      : { weekday, open: false, openTime: "09:00", closeTime: "18:00" };
  });
}

export function ServicesView({ businessId, token }: { businessId: string; token: string }) {
  const [services, setServices] = useState<Service[] | null>(null);
  const [hours, setHours] = useState<HourRow[] | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [newName, setNewName] = useState("");
  const [newDuration, setNewDuration] = useState(60);
  const [newPrice, setNewPrice] = useState("");

  const [importUrl, setImportUrl] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<DraftSuggestion[] | null>(null);
  const [importingSelected, setImportingSelected] = useState(false);

  async function refresh() {
    const [serviceList, hourList, onboardingStatus] = await Promise.all([
      listServices(businessId, token),
      listBusinessHours(businessId, token),
      getOnboarding(businessId, token),
    ]);
    setServices(serviceList);
    setHours(buildHourRows(hourList));
    setOnboarding(onboardingStatus);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [serviceList, hourList, onboardingStatus] = await Promise.all([
          listServices(businessId, token),
          listBusinessHours(businessId, token),
          getOnboarding(businessId, token),
        ]);
        if (!cancelled) {
          setServices(serviceList);
          setHours(buildHourRows(hourList));
          setOnboarding(onboardingStatus);
        }
      } catch {
        if (!cancelled) setError("Nao foi possivel carregar servicos e horarios.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [businessId, token]);

  async function handleQuickStart() {
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      const result = await runQuickStart(businessId, token);
      setInfo(result.message);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel usar as sugestoes.");
    } finally {
      setBusy(false);
    }
  }

  async function handleImportFetch(e: React.FormEvent) {
    e.preventDefault();
    setImportError(null);
    setSuggestions(null);
    setImportBusy(true);
    try {
      const result = await importFromWebsite(businessId, token, importUrl.trim());
      setSuggestions(result.suggestions.map((s) => ({ ...s, selected: true })));
    } catch (err) {
      setImportError(err instanceof ApiError ? err.message : "Nao foi possivel importar dessa URL.");
    } finally {
      setImportBusy(false);
    }
  }

  function updateSuggestion(index: number, patch: Partial<DraftSuggestion>) {
    setSuggestions((prev) => prev?.map((s, i) => (i === index ? { ...s, ...patch } : s)) ?? null);
  }

  async function handleImportConfirm() {
    if (!suggestions) return;
    const toImport = suggestions.filter((s) => s.selected && s.name.trim());
    if (toImport.length === 0) return;
    setImportError(null);
    setImportingSelected(true);
    try {
      for (const s of toImport) {
        await createService(businessId, token, {
          name: s.name.trim(),
          durationMinutes: s.durationMinutes ?? 60,
          price: s.price ?? undefined,
        });
      }
      setSuggestions(null);
      setImportUrl("");
      setInfo(`${toImport.length} servico(s) importado(s).`);
      await refresh();
    } catch (err) {
      setImportError(err instanceof ApiError ? err.message : "Nao foi possivel importar os servicos selecionados.");
    } finally {
      setImportingSelected(false);
    }
  }

  async function handleAddService(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await createService(businessId, token, {
        name: newName.trim(),
        durationMinutes: newDuration,
        price: newPrice.trim() ? Number(newPrice) : undefined,
      });
      setNewName("");
      setNewDuration(60);
      setNewPrice("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel criar o servico.");
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleService(service: Service) {
    setError(null);
    try {
      await updateService(businessId, token, service.id, { active: !service.active });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel atualizar o servico.");
    }
  }

  function updateHourRow(weekday: number, patch: Partial<HourRow>) {
    setHours((prev) => prev?.map((row) => (row.weekday === weekday ? { ...row, ...patch } : row)) ?? null);
  }

  async function handleSaveHours() {
    if (!hours) return;
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      const entries = hours
        .filter((row) => row.open)
        .map((row) => ({ weekday: row.weekday, openTime: row.openTime, closeTime: row.closeTime }));
      await saveBusinessHours(businessId, token, entries);
      setInfo("Horarios salvos.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel salvar os horarios.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h1 className="mb-1 text-lg font-semibold text-zinc-900 dark:text-zinc-50">Serviços e horários</h1>
      <p className="mb-4 max-w-2xl text-xs text-zinc-400">
        O bot só consegue oferecer e confirmar reservas para o que estiver cadastrado aqui.
      </p>

      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      {info && <p className="mb-3 text-sm text-emerald-600">{info}</p>}

      {onboarding && !onboarding.checklist.hasServices && onboarding.template.defaultServices.length > 0 && (
        <div className="mb-6 max-w-2xl rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950/30">
          <p className="text-sm font-medium text-blue-900 dark:text-blue-200">
            Sugestão para {onboarding.template.label}
          </p>
          <p className="mt-1 text-xs text-blue-800 dark:text-blue-300">
            {onboarding.template.defaultServices.map((s) => `${s.name} (${s.durationMinutes}min)`).join(", ")}, com
            horário padrão de segunda a sábado, 9h às 18h.
          </p>
          <button
            onClick={handleQuickStart}
            disabled={busy}
            className="mt-3 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            Usar essas sugestões
          </button>
        </div>
      )}

      <div className="mb-6 max-w-2xl rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Importar do site da empresa</p>
        <p className="mt-1 text-xs text-zinc-400">
          Cole o link do cardápio, tabela de preços ou página de serviços do seu site — a IA lê a página e sugere os
          serviços e preços pra você revisar antes de importar.
        </p>
        <form onSubmit={handleImportFetch} className="mt-3 flex flex-wrap gap-2">
          <input
            required
            type="url"
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
            placeholder="https://seusite.com.br/cardapio"
            className="min-w-64 flex-1 rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button
            type="submit"
            disabled={importBusy}
            className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900"
          >
            {importBusy ? "Analisando..." : "Buscar sugestões"}
          </button>
        </form>

        {importError && <p className="mt-3 text-sm text-red-600">{importError}</p>}

        {suggestions && suggestions.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs text-zinc-400">
              Encontramos {suggestions.length} item(ns). Desmarque o que não quiser, ajuste nome/preço/duração e
              confirme.
            </p>
            <ul className="space-y-2">
              {suggestions.map((s, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2 rounded-md border border-zinc-200 p-2 dark:border-zinc-800">
                  <input
                    type="checkbox"
                    checked={s.selected}
                    onChange={(e) => updateSuggestion(i, { selected: e.target.checked })}
                  />
                  <input
                    value={s.name}
                    onChange={(e) => updateSuggestion(i, { name: e.target.value })}
                    className="min-w-40 flex-1 rounded-md border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  />
                  <input
                    type="number"
                    min={1}
                    value={s.durationMinutes ?? 60}
                    onChange={(e) => updateSuggestion(i, { durationMinutes: Number(e.target.value) })}
                    className="w-20 rounded-md border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  />
                  <span className="text-xs text-zinc-400">min</span>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={s.price ?? ""}
                    onChange={(e) => updateSuggestion(i, { price: e.target.value ? Number(e.target.value) : null })}
                    placeholder="R$ (opcional)"
                    className="w-28 rounded-md border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  />
                </li>
              ))}
            </ul>
            <button
              onClick={handleImportConfirm}
              disabled={importingSelected}
              className="mt-3 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              {importingSelected
                ? "Importando..."
                : `Importar ${suggestions.filter((s) => s.selected).length} selecionado(s)`}
            </button>
          </div>
        )}
      </div>

      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">Serviços</h2>
      {!services && <p className="text-sm text-zinc-400">Carregando...</p>}
      {services && (
        <div className="mb-4 max-w-2xl overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
          {services.length === 0 ? (
            <p className="p-4 text-sm text-zinc-400">Nenhum serviço cadastrado ainda.</p>
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
              {services.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-3 bg-white p-4 dark:bg-zinc-950">
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{s.name}</p>
                    <p className="text-xs text-zinc-400">
                      {s.durationMinutes}min{s.price ? ` · R$ ${Number(s.price).toFixed(2)}` : ""}
                    </p>
                  </div>
                  <button
                    onClick={() => handleToggleService(s)}
                    className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                      s.active
                        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                        : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                    }`}
                  >
                    {s.active ? "Ativo" : "Desativado"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <form onSubmit={handleAddService} className="mb-8 flex max-w-2xl flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-500">Nome do serviço</label>
          <input
            required
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-48 rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-500">Duração (min)</label>
          <input
            type="number"
            required
            min={1}
            value={newDuration}
            onChange={(e) => setNewDuration(Number(e.target.value))}
            className="w-24 rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-500">Preço (opcional)</label>
          <input
            type="number"
            min={0}
            step={0.01}
            value={newPrice}
            onChange={(e) => setNewPrice(e.target.value)}
            placeholder="R$"
            className="w-28 rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900"
        >
          Adicionar
        </button>
      </form>

      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">Horário de funcionamento</h2>
      {!hours && <p className="text-sm text-zinc-400">Carregando...</p>}
      {hours && (
        <div className="max-w-2xl rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <div className="space-y-2">
            {hours.map((row) => (
              <div key={row.weekday} className="flex items-center gap-3">
                <label className="flex w-32 items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                  <input
                    type="checkbox"
                    checked={row.open}
                    onChange={(e) => updateHourRow(row.weekday, { open: e.target.checked })}
                  />
                  {WEEKDAY_LABELS[row.weekday]}
                </label>
                <input
                  type="time"
                  disabled={!row.open}
                  value={row.openTime}
                  onChange={(e) => updateHourRow(row.weekday, { openTime: e.target.value })}
                  className="rounded-md border border-zinc-300 px-2 py-1 text-sm disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900"
                />
                <span className="text-xs text-zinc-400">até</span>
                <input
                  type="time"
                  disabled={!row.open}
                  value={row.closeTime}
                  onChange={(e) => updateHourRow(row.weekday, { closeTime: e.target.value })}
                  className="rounded-md border border-zinc-300 px-2 py-1 text-sm disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900"
                />
              </div>
            ))}
          </div>
          <button
            onClick={handleSaveHours}
            disabled={busy}
            className="mt-4 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900"
          >
            Salvar horários
          </button>
        </div>
      )}
    </div>
  );
}
