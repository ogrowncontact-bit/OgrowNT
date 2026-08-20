"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { JournalPost } from "@inner/db";

const inputClass =
  "w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-3 py-2 text-[14px] text-[var(--inner-ink)] focus:border-[var(--inner-accent)] focus:outline-none";
const btnPrimary = "rounded-[var(--inner-radius-sm)] bg-[var(--inner-ink)] px-3 py-1.5 text-[12px] text-[var(--inner-paper)] disabled:opacity-40";
const btnClass = "rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[12px] text-[var(--inner-ink)] disabled:opacity-40";

export function JournalPostEditor({ post }: { post: JournalPost }) {
  const router = useRouter();
  const [title, setTitle] = useState(post.title);
  const [excerpt, setExcerpt] = useState(post.excerpt);
  const [body, setBody] = useState(post.body);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch(`/api/admin/journal/${post.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, excerpt, body }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to save");
      setMessage("Saved.");
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  async function handleAction(action: "publish" | "unpublish" | "archive") {
    setBusy(true);
    setMessage(null);
    try {
      const res = await fetch(`/api/admin/journal/${post.id}/${action}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `Failed to ${action}`);
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-[13px] text-[var(--inner-muted)]">/journal/{post.slug} · status: {post.status}</p>
          <h1 className="font-display text-[24px] text-[var(--inner-ink)]">{post.title || "Untitled"}</h1>
        </div>
        <div className="flex shrink-0 gap-2">
          <button onClick={handleSave} disabled={saving || busy} className={btnClass}>
            {saving ? "Saving..." : "Save"}
          </button>
          {post.status !== "published" && (
            <button onClick={() => handleAction("publish")} disabled={saving || busy} className={btnPrimary}>
              Publish
            </button>
          )}
          {post.status === "published" && (
            <button onClick={() => handleAction("unpublish")} disabled={saving || busy} className={btnClass}>
              Unpublish
            </button>
          )}
          {post.status !== "archived" && (
            <button onClick={() => handleAction("archive")} disabled={saving || busy} className={btnClass}>
              Archive
            </button>
          )}
        </div>
      </div>

      {message && <p className="mb-4 text-[13px] text-[var(--inner-accent)]">{message}</p>}

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-[12px] font-medium text-[var(--inner-muted)]">Title</label>
          <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-[12px] font-medium text-[var(--inner-muted)]">Excerpt</label>
          <textarea className={inputClass} rows={2} value={excerpt} onChange={(e) => setExcerpt(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-[12px] font-medium text-[var(--inner-muted)]">Body</label>
          <textarea className={inputClass} rows={14} value={body} onChange={(e) => setBody(e.target.value)} />
        </div>
      </div>
    </div>
  );
}
