"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    setLoading(false);
    if (!res.ok) {
      setError("Invalid credentials");
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-base-950 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-lg border border-base-700 bg-base-900 p-8 shadow-xl"
      >
        <h1 className="mb-1 text-lg font-semibold tracking-wide text-ink-100">OgrowNT</h1>
        <p className="mb-6 text-xs text-ink-500">AI Quant System — private access</p>

        <label className="mb-1 block text-xs text-ink-300">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 outline-none focus:border-signal-green"
        />

        <label className="mb-1 block text-xs text-ink-300">Password</label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 outline-none focus:border-signal-green"
        />

        {error && <p className="mb-4 text-xs text-signal-red">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-signal-green/90 py-2 text-sm font-medium text-base-950 transition hover:bg-signal-green disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
