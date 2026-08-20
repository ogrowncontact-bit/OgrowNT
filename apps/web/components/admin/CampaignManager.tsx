"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { CampaignRow } from "@/lib/admin/campaignsReader";

const inputClass =
  "w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-paper)] px-3 py-2 text-[13px] text-[var(--inner-ink)]";
const labelClass = "mb-1 block text-[12px] text-[var(--inner-muted)]";

interface AssessmentOption {
  id: string;
  name: string;
  slug: string;
}

export function CampaignManager({ campaigns, assessments }: { campaigns: CampaignRow[]; assessments: AssessmentOption[] }) {
  const router = useRouter();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", source: "", medium: "", campaignParam: "", landingSlug: "", assessmentId: "", budgetNotes: "", creativeName: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to create");
      setForm({ name: "", source: "", medium: "", campaignParam: "", landingSlug: "", assessmentId: "", budgetNotes: "", creativeName: "" });
      setShowForm(false);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  async function setStatus(id: string, status: string) {
    await fetch(`/api/admin/campaigns/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    router.refresh();
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-[13px] text-[var(--inner-ink-soft)]">Attribution management only — no advertising API connected.</p>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-[var(--inner-radius-sm)] bg-[var(--inner-accent)] px-3 py-1.5 text-[13px] font-medium text-[var(--inner-accent-contrast)]"
        >
          {showForm ? "Cancel" : "+ New campaign"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 space-y-3 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className={labelClass}>Campaign name</label>
              <input value={form.name} onChange={(e) => update("name", e.target.value)} className={inputClass} required />
            </div>
            <div>
              <label className={labelClass}>Creative name</label>
              <input value={form.creativeName} onChange={(e) => update("creativeName", e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Source (utm_source)</label>
              <input value={form.source} onChange={(e) => update("source", e.target.value)} className={inputClass} required />
            </div>
            <div>
              <label className={labelClass}>Medium (utm_medium)</label>
              <input value={form.medium} onChange={(e) => update("medium", e.target.value)} className={inputClass} required />
            </div>
            <div>
              <label className={labelClass}>Campaign param (utm_campaign)</label>
              <input value={form.campaignParam} onChange={(e) => update("campaignParam", e.target.value)} className={inputClass} required />
            </div>
            <div>
              <label className={labelClass}>Landing slug</label>
              <input value={form.landingSlug} onChange={(e) => update("landingSlug", e.target.value)} placeholder="love" className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Assessment</label>
              <select value={form.assessmentId} onChange={(e) => update("assessmentId", e.target.value)} className={inputClass}>
                <option value="">—</option>
                {assessments.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className={labelClass}>Budget notes</label>
              <input value={form.budgetNotes} onChange={(e) => update("budgetNotes", e.target.value)} className={inputClass} />
            </div>
          </div>
          {error && <p className="text-[13px] text-[var(--inner-accent)]">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-[var(--inner-radius-sm)] bg-[var(--inner-ink)] px-4 py-2 text-[13px] text-[var(--inner-paper)] disabled:opacity-40"
          >
            {submitting ? "Creating..." : "Create"}
          </button>
        </form>
      )}

      <div className="overflow-x-auto rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)]">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
              <th className="whitespace-nowrap px-4 py-3 font-medium">Campaign</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Source / Medium</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Landing</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Status</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Sessions</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Paid</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((c) => (
              <tr key={c.id} className="border-b border-[var(--inner-line)] last:border-0">
                <td className="px-4 py-3">
                  <p className="font-medium text-[var(--inner-ink)]">{c.name}</p>
                  {c.creativeName && <p className="text-[12px] text-[var(--inner-muted)]">{c.creativeName}</p>}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">
                  {c.source} / {c.medium}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{c.landingSlug ? `/${c.landingSlug}` : "—"}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{c.status}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{c.sessions}</td>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--inner-ink-soft)]">{c.paidOrders}</td>
                <td className="whitespace-nowrap px-4 py-3">
                  {c.status !== "active" && (
                    <button onClick={() => setStatus(c.id, "active")} className="mr-2 text-[12px] text-[var(--inner-accent)]">
                      Activate
                    </button>
                  )}
                  {c.status === "active" && (
                    <button onClick={() => setStatus(c.id, "paused")} className="mr-2 text-[12px] text-[var(--inner-muted)]">
                      Pause
                    </button>
                  )}
                  {c.status !== "ended" && (
                    <button onClick={() => setStatus(c.id, "ended")} className="text-[12px] text-[var(--inner-muted)]">
                      End
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {campaigns.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-[var(--inner-muted)]">
                  No campaigns yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
