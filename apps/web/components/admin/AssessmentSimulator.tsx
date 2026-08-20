"use client";

import { useState } from "react";
import type { SessionState } from "@inner/assessment-engine";
import type { ClientQuestion } from "@/lib/clientQuestion";

interface SimulateResponse {
  state: SessionState;
  question: ClientQuestion | null;
  isComplete: boolean;
  progress: { asked: number; recommended: number; max: number };
}

const btnPrimary = "rounded-[var(--inner-radius-sm)] bg-[var(--inner-ink)] px-3 py-1.5 text-[12px] text-[var(--inner-paper)] disabled:opacity-40";
const btnSecondary = "rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[12px] text-[var(--inner-ink)] disabled:opacity-40";

export function AssessmentSimulator({ assessmentId }: { assessmentId: string }) {
  const [sim, setSim] = useState<SimulateResponse | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [scaleValue, setScaleValue] = useState<number | undefined>(undefined);
  const [openText, setOpenText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function call(body: Record<string, unknown>) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/assessments/${assessmentId}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error ?? "Simulation step failed");
      setSim(data);
      setSelected([]);
      setScaleValue(undefined);
      setOpenText("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function handleStart() {
    call({});
  }

  function handleAnswer(skipped = false) {
    if (!sim?.question) return;
    const q = sim.question;
    const answer: Record<string, unknown> = { questionKey: q.key, skipped };
    if (!skipped) {
      if (q.type === "open_text") answer.openText = openText.trim();
      else if (q.type === "scale") answer.scaleValue = scaleValue;
      else answer.selectedOptionKeys = selected;
    }
    call({ state: sim.state, answer });
  }

  function toggleOption(key: string, multi: boolean) {
    setSelected((prev) => (multi ? (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]) : [key]));
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-paper)] p-6">
        {!sim && (
          <button onClick={handleStart} disabled={loading} className={btnPrimary}>
            {loading ? "Starting..." : "Start simulation"}
          </button>
        )}

        {sim && !sim.isComplete && sim.question && (
          <div>
            <p className="mb-1 text-[12px] text-[var(--inner-muted)]">
              Question {sim.progress.asked + 1} of about {sim.progress.recommended} (max {sim.progress.max})
            </p>
            <h2 className="font-display mb-4 text-[18px] text-[var(--inner-ink)]">{sim.question.prompt}</h2>

            {(sim.question.type === "single_select" || sim.question.type === "multi_select") && (
              <div className="mb-4 space-y-2">
                {sim.question.options?.map((o) => (
                  <label key={o.key} className="flex items-center gap-2 text-[13px] text-[var(--inner-ink)]">
                    <input
                      type={sim.question!.type === "multi_select" ? "checkbox" : "radio"}
                      checked={selected.includes(o.key)}
                      onChange={() => toggleOption(o.key, sim.question!.type === "multi_select")}
                    />
                    {o.label}
                  </label>
                ))}
              </div>
            )}

            {sim.question.type === "scale" && (
              <div className="mb-4 flex gap-2">
                {Array.from({ length: sim.question.scaleMax ?? 5 }, (_, i) => i + 1).map((n) => (
                  <button
                    key={n}
                    onClick={() => setScaleValue(n)}
                    className={scaleValue === n ? btnPrimary : btnSecondary}
                  >
                    {n}
                  </button>
                ))}
              </div>
            )}

            {sim.question.type === "open_text" && (
              <textarea
                className="mb-4 w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-2 text-[13px]"
                rows={3}
                value={openText}
                onChange={(e) => setOpenText(e.target.value)}
              />
            )}

            <div className="flex items-center gap-2">
              <button onClick={() => handleAnswer(false)} disabled={loading} className={btnPrimary}>
                {loading ? "..." : "Answer"}
              </button>
              {sim.question.sensitive && (
                <button onClick={() => handleAnswer(true)} disabled={loading} className={btnSecondary}>
                  Skip (Prefer not to answer)
                </button>
              )}
            </div>
          </div>
        )}

        {sim?.isComplete && (
          <div>
            <p className="font-display mb-2 text-[16px] text-[var(--inner-ink)]">Simulation complete</p>
            <p className="mb-4 text-[13px] text-[var(--inner-ink-soft)]">
              {sim.progress.asked} questions asked. Restart to try a different path.
            </p>
            <button onClick={handleStart} disabled={loading} className={btnPrimary}>
              Restart
            </button>
          </div>
        )}

        {error && (
          <p role="alert" className="mt-4 text-[12px] text-[var(--inner-accent)]">
            {error}
          </p>
        )}
      </div>

      <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4">
        <p className="mb-3 text-[12px] font-medium text-[var(--inner-ink)]">
          Live dimension state — never shown to real users, admin diagnostic only
        </p>
        {!sim && <p className="text-[12px] text-[var(--inner-muted)]">Start a simulation to see dimension state.</p>}
        {sim && (
          <div className="space-y-2">
            {Object.entries(sim.state.dimensionScores).map(([key, d]) => (
              <div key={key} className="text-[12px]">
                <div className="flex justify-between text-[var(--inner-ink-soft)]">
                  <span>{key}</span>
                  <span>
                    {d.normalized.toFixed(0)} · confidence {d.confidence.toFixed(2)} · consistency {d.consistency.toFixed(2)}
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full rounded-full bg-[var(--inner-line)]">
                  <div className="h-1.5 rounded-full bg-[var(--inner-accent)]" style={{ width: `${d.normalized}%` }} />
                </div>
              </div>
            ))}
            <p className="mt-3 text-[11px] text-[var(--inner-muted)]">
              Asked: {sim.state.askedQuestionKeys.join(", ") || "—"}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
