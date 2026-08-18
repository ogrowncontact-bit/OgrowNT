"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type Action = "unpublish" | "republish" | "archive" | "restore";

const CONFIRM_MESSAGE: Record<Action, string | null> = {
  unpublish: "Take this experience offline immediately? It stops serving on the very next request.",
  archive: "Archive this experience? It will come offline and move out of the normal draft/publish flow.",
  republish: null,
  restore: null,
};

const LABEL: Record<Action, string> = {
  unpublish: "Unpublish",
  republish: "Republish",
  archive: "Archive",
  restore: "Restore to draft",
};

function ActionButton({ assessmentId, action }: { assessmentId: string; action: Action }) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    const confirmMessage = CONFIRM_MESSAGE[action];
    if (confirmMessage && !window.confirm(confirmMessage)) return;

    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/assessments/${assessmentId}/${action}`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.error ?? `Failed to ${action}`);
      }
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <button
        onClick={handleClick}
        disabled={submitting}
        className="text-[12px] text-[var(--inner-accent)] underline underline-offset-2 disabled:opacity-40"
      >
        {submitting ? "Working..." : LABEL[action]}
      </button>
      {error && (
        <p role="alert" className="mt-1 text-[11px] text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </div>
  );
}

export function AssessmentStatusActions({
  assessmentId,
  status,
  hasPublishedVersion,
}: {
  assessmentId: string;
  status: "draft" | "published" | "archived";
  hasPublishedVersion: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-3">
      {status === "published" && <ActionButton assessmentId={assessmentId} action="unpublish" />}
      {status === "draft" && hasPublishedVersion && <ActionButton assessmentId={assessmentId} action="republish" />}
      {status !== "archived" && <ActionButton assessmentId={assessmentId} action="archive" />}
      {status === "archived" && <ActionButton assessmentId={assessmentId} action="restore" />}
    </div>
  );
}
