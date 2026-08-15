"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
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
  const [question, setQuestion] = useState(initialQuestion);
  const [progress, setProgress] = useState(initialProgress);
  const [selected, setSelected] = useState<string[]>([]);
  const [scaleValue, setScaleValue] = useState<number | undefined>(undefined);
  const [openText, setOpenText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
          {error && <p className="mt-3 text-sm text-[var(--inner-accent)]">{error}</p>}
        </>
      }
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={question.key}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -16 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
        >
          <h1 className="font-display text-[26px] leading-snug text-[var(--inner-ink)]">{question.prompt}</h1>

          <div className="mt-8 space-y-3">
            {question.type === "open_text" && (
              <OpenTextArea value={openText} onChange={setOpenText} />
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

            {(question.type === "single_select" || question.type === "multi_select") &&
              question.options?.map((option) => (
                <OptionCard
                  key={option.key}
                  label={option.label}
                  selected={selected.includes(option.key)}
                  onClick={() => toggleOption(option.key)}
                />
              ))}
          </div>
        </motion.div>
      </AnimatePresence>
    </Screen>
  );
}
