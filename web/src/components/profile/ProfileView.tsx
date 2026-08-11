"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { getBusinessProfile, updateBusinessProfile } from "@/lib/business";
import type { BusinessProfile } from "@/lib/types";

const CURRENCIES = [
  { value: "EUR", label: "Euro (EUR)" },
  { value: "BRL", label: "Real brasileiro (BRL)" },
  { value: "USD", label: "Dólar americano (USD)" },
  { value: "GBP", label: "Libra esterlina (GBP)" },
];

const LANGUAGES = [
  { value: "pt", label: "Português" },
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
  { value: "it", label: "Italiano" },
  { value: "nl", label: "Nederlands" },
];

export function ProfileView({ businessId, token }: { businessId: string; token: string }) {
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [currency, setCurrency] = useState("EUR");
  const [defaultLanguage, setDefaultLanguage] = useState("pt");
  const [supportedLanguages, setSupportedLanguages] = useState<string[]>(["pt"]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getBusinessProfile(businessId, token);
        if (cancelled) return;
        setProfile(data);
        setName(data.name);
        setDescription(data.description ?? "");
        setAddress(data.address ?? "");
        setPhone(data.phone ?? "");
        setCurrency(data.currency);
        setDefaultLanguage(data.defaultLanguage);
        setSupportedLanguages(data.supportedLanguages);
      } catch {
        if (!cancelled) setError("Nao foi possivel carregar o perfil da empresa.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [businessId, token]);

  function toggleLanguage(code: string) {
    setSupportedLanguages((prev) => (prev.includes(code) ? prev.filter((l) => l !== code) : [...prev, code]));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (supportedLanguages.length === 0) {
      setError("Selecione pelo menos um idioma suportado.");
      return;
    }
    if (!supportedLanguages.includes(defaultLanguage)) {
      setError("O idioma padrao precisa estar entre os idiomas suportados.");
      return;
    }

    setSaving(true);
    try {
      const updated = await updateBusinessProfile(businessId, token, {
        name: name.trim(),
        description: description.trim() || null,
        address: address.trim() || null,
        phone: phone.trim() || null,
        currency,
        defaultLanguage,
        supportedLanguages,
      });
      setProfile(updated);
      setSuccess("Perfil atualizado.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel salvar o perfil.");
    } finally {
      setSaving(false);
    }
  }

  if (!profile && !error) {
    return (
      <div className="flex-1 overflow-y-auto p-6">
        <p className="text-sm text-zinc-400">Carregando...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h1 className="mb-1 text-lg font-semibold text-zinc-900 dark:text-zinc-50">Perfil da empresa</h1>
      <p className="mb-4 max-w-2xl text-xs text-zinc-400">
        Esses dados aparecem pro cliente na conversa de WhatsApp e definem em que moeda e idioma o bot fala por
        padrão.
      </p>

      <form onSubmit={handleSubmit} className="max-w-xl space-y-4 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Nome da empresa</label>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Descrição</label>
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Endereço</label>
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Telefone</label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Moeda</label>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            {CURRENCIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-zinc-400">
            Usada pra mostrar os preços dos seus serviços pro cliente no WhatsApp e no painel.
          </p>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Idiomas suportados</label>
          <div className="flex flex-wrap gap-3">
            {LANGUAGES.map((l) => (
              <label key={l.value} className="flex items-center gap-1.5 text-sm text-zinc-700 dark:text-zinc-300">
                <input
                  type="checkbox"
                  checked={supportedLanguages.includes(l.value)}
                  onChange={() => toggleLanguage(l.value)}
                />
                {l.label}
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Idioma padrão</label>
          <select
            value={defaultLanguage}
            onChange={(e) => setDefaultLanguage(e.target.value)}
            className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            {LANGUAGES.filter((l) => supportedLanguages.includes(l.value)).map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {success && <p className="text-sm text-emerald-600">{success}</p>}

        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900"
        >
          {saving ? "Salvando..." : "Salvar"}
        </button>
      </form>
    </div>
  );
}
