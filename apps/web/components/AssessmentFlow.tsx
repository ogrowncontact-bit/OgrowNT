"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Screen, ProgressBar, OptionCard, Button, ScaleInput, OpenTextArea } from "@inner/ui";
import type { ClientQuestion } from "@/lib/clientQuestion";

interface Progress {
  asked: number;
  recommended: number;
  max: number;
}

interface AssessmentFlowProps {
  slug: string;
  assessmentSessionId: string;
  initialQuestion: ClientQuestion;
  initialProgress: Progress;
}

export function AssessmentFlow({ slug, assessmentSessionId, initialQuestion, initialProgress }: AssessmentFlowProps) {
  const router = useRouter();
  const reducedMotion = useReducedMotion();
  const [question, setQuestion] = useState(initialQuestion);
  const [progress, setProgress] = useState(initialProgress);
  const [selected, setSelected] = useState<string[]>([]);
  const [scaleValue, setScaleValue] = useState<number | undefined>(undefined);
  const [openText, setOpenText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [supportMessage, setSupportMessage] = useState<string | null>(null);

  function toggleOption(key: string) {
    if (question.type === "multi_select") {
      setSelected((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
    } else {
      setSelected([key]);
    }
  }

  const canContinue =
    question.type === "open_text"
      ? openText.trim().length > 0
      : question.type === "scale"
        ? scaleValue !== undefined
        : selected.length > 0;

  async function handleContinue() {
    if (!canContinue || submitting) return;
    setSubmitting(true);
    setError(null);

    const payload: Record<string, unknown> = { questionKey: question.key };
    if (question.type === "open_text") payload.openText = openText.trim();
    else if (question.type === "scale") payload.scaleValue = scaleValue;
    else payload.selectedOptionKeys = selected;

    try {
      const res = await fetch(`/api/sessions/${assessmentSessionId}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Couldn't save that answer — please try again.");
      const data = await res.json();

      setSupportMessage(data.supportResources ?? null);

      if (data.isComplete) {
        router.push(`/${slug}/session/${assessmentSessionId}/result`);
        return;
      }

      setQuestion(data.nextQuestion);
      setProgress(data.progress);
      setSelected([]);
      setScaleValue(undefined);
      setOpenText("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Screen
      align="top"
      eyebrow={
        <ProgressBar
          current={progress.asked + 1}
          approxTotal={progress.recommended}
          label={`Question ${progress.asked + 1} of about ${progress.recommended}`}
        />
      }
      footer={
        <>
          <Button onClick={handleContinue} disabled={!canContinue || submitting}>
            {submitting ? "..." : "Continue"}
          </Button>
          {error && (
            <p role="alert" className="mt-3 text-sm text-[var(--inner-accent)]">
              {error}
            </p>
          )}
        </>
      }
    >
      {/* A stable (non-keyed) live region wrapping the keyed AnimatePresence content: screen
          readers announce the new question as it swaps in, without stealing keyboard focus
          from the Continue button the way moving focus to the heading would. */}
      <div aria-live="polite" aria-atomic="true">
        <AnimatePresence mode="wait">
          <motion.div
            key={question.key}
            initial={reducedMotion ? false : { opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reducedMotion ? undefined : { opacity: 0, x: -16 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            {supportMessage && (
              <div
                role="status"
                className="mb-6 rounded-[var(--inner-radius-md)] border border-[var(--inner-accent-soft)] bg-[var(--inner-card)] p-4"
              >
                <p className="text-[14px] leading-relaxed text-[var(--inner-ink-soft)]">{supportMessage}</p>
              </div>
            )}

            <h1 id="question-heading" className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">
              {question.prompt}
            </h1>

            <div className="mt-8 space-y-3">
              {question.type === "open_text" && (
                <>
                  <label htmlFor="open-text-answer" className="sr-only">
                    {question.prompt}
                  </label>
                  <OpenTextArea id="open-text-answer" value={openText} onChange={setOpenText} />
                </>
              )}

              {question.type === "scale" && question.scaleMax && (
                <ScaleInput
                  max={question.scaleMax}
                  value={scaleValue}
                  onChange={setScaleValue}
                  lowLabel="Not much"
                  highLabel="A lot"
                />
              )}

              {(question.type === "single_select" || question.type === "multi_select") && (
                <div
                  role={question.type === "single_select" ? "radiogroup" : "group"}
                  aria-labelledby="question-heading"
                  className="space-y-3"
                >
                  {question.options?.map((option) => (
                    <OptionCard
                      key={option.key}
                      variant={question.type === "single_select" ? "radio" : "checkbox"}
                      label={option.label}
                      selected={selected.includes(option.key)}
                      onClick={() => toggleOption(option.key)}
                    />
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </Screen>
  );
}
