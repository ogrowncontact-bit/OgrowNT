"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const inputClass =
  "w-full rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-4 py-3 text-[15px] text-[var(--inner-ink)] focus:border-[var(--inner-accent)] focus:outline-none";

export function NewAssessmentForm() {
  const router = useRouter();
  const [form, setForm] = useState({ slug: "", name: "", category: "", hook: "", description: "", targetAudience: "" });
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
      const res = await fetch("/api/admin/assessments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to create");
      router.push(`/admin/assessments/${data.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Slug (URL path, e.g. "attachment-style")</label>
        <input value={form.slug} onChange={(e) => update("slug", e.target.value)} className={inputClass} required />
      </div>
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Name (e.g. "Your Attachment Style")</label>
        <input value={form.name} onChange={(e) => update("name", e.target.value)} className={inputClass} required />
      </div>
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Category</label>
        <input value={form.category} onChange={(e) => update("category", e.target.value)} className={inputClass} required />
      </div>
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Hook (landing page headline)</label>
        <input value={form.hook} onChange={(e) => update("hook", e.target.value)} className={inputClass} required />
      </div>
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Description</label>
        <textarea value={form.description} onChange={(e) => update("description", e.target.value)} className={inputClass} rows={2} required />
      </div>
      <div>
        <label className="mb-1 block text-[13px] text-[var(--inner-muted)]">Target audience</label>
        <input value={form.targetAudience} onChange={(e) => update("targetAudience", e.target.value)} className={inputClass} required />
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
