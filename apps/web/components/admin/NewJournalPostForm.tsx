"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const inputClass =
  "w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-3 text-[15px] text-[var(--inner-ink)] focus:border-[var(--inner-accent)] focus:outline-none";

export function NewJournalPostForm() {
  const router = useRouter();
  const [form, setForm] = useState({ slug: "", title: "", excerpt: "", body: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/journal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to create");
      router.push(`/admin/journal/${data.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Slug (URL path, e.g. "understanding-attachment")</label>
        <input value={form.slug} onChange={(e) => update("slug", e.target.value)} className={inputClass} required />
      </div>
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Title</label>
        <input value={form.title} onChange={(e) => update("title", e.target.value)} className={inputClass} required />
      </div>
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Excerpt (shown on /journal)</label>
        <textarea value={form.excerpt} onChange={(e) => update("excerpt", e.target.value)} className={inputClass} rows={2} required />
      </div>
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Body (paragraphs separated by a blank line)</label>
        <textarea value={form.body} onChange={(e) => update("body", e.target.value)} className={inputClass} rows={8} required />
      </div>
      {error && (
        <p role="alert" className="text-sm text-[var(--inner-accent)]">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="rounded-[var(--inner-radius-md)] bg-[var(--inner-accent)] px-6 py-3 text-[15px] font-medium text-[var(--inner-accent-contrast)] disabled:opacity-40"
      >
        {submitting ? "Creating..." : "Create draft"}
      </button>
    </form>
  );
}
