"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { ApiError } from "@/lib/api";

const INDUSTRIES = [
  { value: "RESTAURANT", label: "Restaurante" },
  { value: "COFFEE_SHOP", label: "Cafeteria" },
  { value: "EQUESTRIAN", label: "Hípica / Centro equestre" },
  { value: "KITE_SCHOOL", label: "Escola de kitesurf" },
  { value: "HOSTEL", label: "Hostel / Pousada" },
  { value: "OTHER", label: "Outro" },
] as const;

export default function RegisterPage() {
  const { token, loading, register } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [industry, setIndustry] = useState<string>(INDUSTRIES[0].value);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && token) router.replace("/inbox");
  }, [loading, token, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({ name, email, password, businessName, industry });
      router.replace("/inbox");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nao foi possivel criar a conta. Tente novamente.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 px-4 py-8 dark:bg-black">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
      >
        <h1 className="mb-1 text-xl font-semibold text-zinc-900 dark:text-zinc-50">Criar conta</h1>
        <p className="mb-6 text-sm text-zinc-500">Cadastre sua empresa no AI Front Desk.</p>

        <label className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">Seu nome</label>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mb-4 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
        />

        <label className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
          placeholder="voce@empresa.com"
        />

        <label className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">Senha</label>
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
          placeholder="Pelo menos 8 caracteres"
        />

        <label className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">Nome da empresa</label>
        <input
          required
          value={businessName}
          onChange={(e) => setBusinessName(e.target.value)}
          className="mb-4 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
        />

        <label className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">Tipo de negocio</label>
        <select
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="mb-4 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
        >
          {INDUSTRIES.map((i) => (
            <option key={i.value} value={i.value}>
              {i.label}
            </option>
          ))}
        </select>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900"
        >
          {submitting ? "Criando..." : "Criar conta"}
        </button>

        <p className="mt-4 text-center text-sm text-zinc-500">
          Ja tem conta?{" "}
          <Link href="/login" className="font-medium text-zinc-900 dark:text-zinc-50">
            Entrar
          </Link>
        </p>
      </form>
    </div>
  );
}
