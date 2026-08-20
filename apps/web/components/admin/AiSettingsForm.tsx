"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const inputClass =
  "w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-paper)] px-3 py-2 text-[13px] text-[var(--inner-ink)]";
const labelClass = "mb-1 block text-[12px] text-[var(--inner-muted)]";

export interface AiSettingsFormProps {
  initial: {
    fastModel: string;
    qualityModel: string;
    temperature: number;
    maxTokens: number;
    timeoutMs: number;
  };
  readOnly: boolean;
}

export function AiSettingsForm({ initial, readOnly }: AiSettingsFormProps) {
  const router = useRouter();
  const [fastModel, setFastModel] = useState(initial.fastModel);
  const [qualityModel, setQualityModel] = useState(initial.qualityModel);
  const [temperature, setTemperature] = useState(String(initial.temperature));
  const [maxTokens, setMaxTokens] = useState(String(initial.maxTokens));
  const [timeoutMs, setTimeoutMs] = useState(String(initial.timeoutMs));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSaved(false);
    try {
      const res = await fetch("/api/admin/ai-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fastModel,
          qualityModel,
          temperature: Number(temperature),
          maxTokens: Number(maxTokens),
          timeoutMs: Number(timeoutMs),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.error ?? "Failed to save settings");
      }
      setSaved(true);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-lg space-y-5">
      <div>
        <label className={labelClass} htmlFor="fastModel">
          Fast model
        </label>
        <input
          id="fastModel"
          value={fastModel}
          onChange={(e) => setFastModel(e.target.value)}
          disabled={readOnly}
          className={inputClass}
        />
        <p className="mt-1 text-[11px] text-[var(--inner-muted)]">
          Used in the live conversation's critical path (Question AI, Response AI) — latency matters more than depth here.
        </p>
      </div>

      <div>
        <label className={labelClass} htmlFor="qualityModel">
          Quality model
        </label>
        <input
          id="qualityModel"
          value={qualityModel}
          onChange={(e) => setQualityModel(e.target.value)}
          disabled={readOnly}
          className={inputClass}
        />
        <p className="mt-1 text-[11px] text-[var(--inner-muted)]">
          Used for the premium report and profile enrichment — generation quality matters more than speed.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className={labelClass} htmlFor="temperature">
            Temperature
          </label>
          <input
            id="temperature"
            type="number"
            step="0.1"
            min="0"
            max="1"
            value={temperature}
            onChange={(e) => setTemperature(e.target.value)}
            disabled={readOnly}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="maxTokens">
            Max tokens
          </label>
          <input
            id="maxTokens"
            type="number"
            min="1"
            max="8192"
            value={maxTokens}
            onChange={(e) => setMaxTokens(e.target.value)}
            disabled={readOnly}
            className={inputClass}
          />
          <p className="mt-1 text-[11px] text-[var(--inner-muted)]">Ceiling — each call still requests only what it needs.</p>
        </div>
        <div>
          <label className={labelClass} htmlFor="timeoutMs">
            Timeout (ms)
          </label>
          <input
            id="timeoutMs"
            type="number"
            min="1000"
            max="120000"
            value={timeoutMs}
            onChange={(e) => setTimeoutMs(e.target.value)}
            disabled={readOnly}
            className={inputClass}
          />
        </div>
      </div>

      {!readOnly && (
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-[var(--inner-radius-sm)] bg-[var(--inner-ink)] px-4 py-2 text-[13px] text-[var(--inner-paper)] disabled:opacity-40"
          >
            {submitting ? "Saving..." : "Save settings"}
          </button>
          {saved && <span className="text-[12px] text-[var(--inner-ink-soft)]">Saved.</span>}
        </div>
      )}
      {readOnly && <p className="text-[12px] text-[var(--inner-muted)]">Viewers can see AI settings but can't change them.</p>}
      {error && (
        <p role="alert" className="text-[12px] text-[var(--inner-accent)]">
          {error}
        </p>
      )}
    </form>
  );
}
