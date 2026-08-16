"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function AdminLoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => null))?.error ?? "Invalid email or password.");
      router.push("/admin");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <input
        type="email"
        placeholder="Email"
        autoComplete="username"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-3 text-[15px] text-[var(--inner-ink)] focus:border-[var(--inner-accent)] focus:outline-none"
      />
      <input
        type="password"
        placeholder="Password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-3 text-[15px] text-[var(--inner-ink)] focus:border-[var(--inner-accent)] focus:outline-none"
      />
      {error && <p className="text-sm text-[var(--inner-accent)]">{error}</p>}
      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-6 py-3 text-[15px] font-medium text-[var(--inner-accent-contrast)] disabled:opacity-40"
      >
        {submitting ? "..." : "Sign in"}
      </button>
    </form>
  );
}
