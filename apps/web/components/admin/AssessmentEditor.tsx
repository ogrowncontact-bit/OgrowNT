"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { validateAssessmentConfig, type DimensionDefinition } from "@inner/content";
import type {
  AssessmentConfig,
  Question,
  QuestionOption,
  QuestionType,
  AdaptiveRule,
  ProfileDefinition,
  ReportSection,
  RecommendationCandidate,
} from "@inner/assessment-engine";

const input =
  "w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-card)] px-3 py-2 text-[14px] text-[var(--inner-ink)] focus:border-[var(--inner-accent)] focus:outline-none";
const label = "mb-1 block text-[12px] font-medium text-[var(--inner-muted)]";
const smallBtn = "rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[13px] text-[var(--inner-ink-soft)] hover:border-[var(--inner-accent-soft)]";
const removeBtn = "text-[12px] text-[var(--inner-accent)]";
const CURRENCIES = ["EUR", "USD", "GBP", "BRL"];

function Section({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  return (
    <details open={defaultOpen} className="mb-4 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
      <summary className="cursor-pointer font-display text-[17px] text-[var(--inner-ink)]">{title}</summary>
      <div className="mt-4">{children}</div>
    </details>
  );
}

interface Props {
  assessmentId: string;
  initialConfig: AssessmentConfig;
  hasDraft: boolean;
  status: "draft" | "published" | "archived";
  dimensionPool: DimensionDefinition[];
  otherAssessmentSlugs: string[];
}

export function AssessmentEditor({ assessmentId, initialConfig, hasDraft, status, dimensionPool, otherAssessmentSlugs }: Props) {
  const router = useRouter();
  const [config, setConfig] = useState<AssessmentConfig>(initialConfig);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const chosenDimensionKeys = config.dimensions.map((d) => d.key);

  function patch(fields: Partial<AssessmentConfig>) {
    setConfig((prev) => ({ ...prev, ...fields }));
    setSavedMessage(null);
  }

  async function handleSave(): Promise<boolean> {
    setSaving(true);
    setErrors([]);
    setSavedMessage(null);
    try {
      const res = await fetch(`/api/admin/assessments/${assessmentId}/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      if (!res.ok) {
        setErrors(data.violations ?? [data.error ?? "Failed to save"]);
        return false;
      }
      setSavedMessage("Draft saved.");
      router.refresh();
      return true;
    } catch (e) {
      setErrors([e instanceof Error ? e.message : "Something went wrong."]);
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    setPublishing(true);
    const saved = await handleSave();
    if (saved) {
      const res = await fetch(`/api/admin/assessments/${assessmentId}/publish`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) setErrors([data.error ?? "Failed to publish"]);
      else {
        setSavedMessage("Published — live now.");
        router.refresh();
      }
    }
    setPublishing(false);
  }

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-[13px] text-[var(--inner-muted)]">
            /{config.slug} · status: {status}
            {hasDraft && status === "published" ? " (editing unpublished draft)" : ""}
          </p>
          <h1 className="font-display text-[24px] text-[var(--inner-ink)]">{config.name || "Untitled experience"}</h1>
        </div>
        <div className="flex shrink-0 gap-2">
          <a href={`/admin/assessments/${assessmentId}/simulate`} className={smallBtn}>
            Simulate
          </a>
          <button onClick={handleSave} disabled={saving || publishing} className={smallBtn}>
            {saving ? "Saving..." : "Save draft"}
          </button>
          <button
            onClick={handlePublish}
            disabled={saving || publishing}
            className="rounded-[var(--inner-radius-sm)] bg-[var(--inner-accent)] px-3 py-1.5 text-[13px] font-medium text-[var(--inner-accent-contrast)] disabled:opacity-40"
          >
            {publishing ? "Publishing..." : "Publish"}
          </button>
        </div>
      </div>

      {savedMessage && <p className="mb-4 text-[13px] text-[var(--inner-accent)]">{savedMessage}</p>}
      {errors.length > 0 && (
        <div className="mb-4 rounded-[var(--inner-radius-md)] border border-[var(--inner-accent)] bg-[var(--inner-card)] p-4">
          <p className="mb-1 text-[13px] font-medium text-[var(--inner-accent)]">Couldn&apos;t save:</p>
          <ul className="list-inside list-disc text-[13px] text-[var(--inner-ink-soft)]">
            {errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <Section title="Overview" defaultOpen>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className={label}>Name</label>
            <input className={input} value={config.name} onChange={(e) => patch({ name: e.target.value })} />
          </div>
          <div>
            <label className={label}>Category</label>
            <input className={input} value={config.category} onChange={(e) => patch({ category: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className={label}>Hook (landing headline)</label>
            <input className={input} value={config.hook} onChange={(e) => patch({ hook: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className={label}>Description</label>
            <textarea className={input} rows={2} value={config.description} onChange={(e) => patch({ description: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className={label}>Target audience</label>
            <input className={input} value={config.targetAudience} onChange={(e) => patch({ targetAudience: e.target.value })} />
          </div>
          <div>
            <label className={label}>Min questions</label>
            <input type="number" className={input} value={config.minQuestions} onChange={(e) => patch({ minQuestions: Number(e.target.value) })} />
          </div>
          <div>
            <label className={label}>Recommended questions</label>
            <input
              type="number"
              className={input}
              value={config.recommendedQuestions}
              onChange={(e) => patch({ recommendedQuestions: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className={label}>Max questions</label>
            <input type="number" className={input} value={config.maxQuestions} onChange={(e) => patch({ maxQuestions: Number(e.target.value) })} />
          </div>
          <div>
            <label className={label}>AI influence cap (0-1)</label>
            <input
              type="number"
              step="0.01"
              className={input}
              value={config.scoringModel.aiInfluenceCap}
              onChange={(e) => patch({ scoringModel: { ...config.scoringModel, aiInfluenceCap: Number(e.target.value) } })}
            />
          </div>
        </div>
      </Section>

      <Section title="Free result copy">
        <div className="space-y-3">
          <div>
            <label className={label}>Headline</label>
            <input
              className={input}
              value={config.freeResultTemplate.headline}
              onChange={(e) => patch({ freeResultTemplate: { ...config.freeResultTemplate, headline: e.target.value } })}
            />
          </div>
          <div>
            <label className={label}>Insight intro</label>
            <textarea
              className={input}
              rows={2}
              value={config.freeResultTemplate.insightIntro}
              onChange={(e) => patch({ freeResultTemplate: { ...config.freeResultTemplate, insightIntro: e.target.value } })}
            />
          </div>
          <div>
            <label className={label}>Locked insights label</label>
            <input
              className={input}
              value={config.freeResultTemplate.lockedInsightsLabel}
              onChange={(e) => patch({ freeResultTemplate: { ...config.freeResultTemplate, lockedInsightsLabel: e.target.value } })}
            />
          </div>
        </div>
      </Section>

      <Section title={`Dimensions (${config.dimensions.length} selected)`}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {dimensionPool.map((dim) => {
            const existing = config.dimensions.find((d) => d.key === dim.key);
            return (
              <div key={dim.key} className="flex items-center gap-2 rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] p-2">
                <input
                  type="checkbox"
                  checked={!!existing}
                  onChange={(e) => {
                    if (e.target.checked) patch({ dimensions: [...config.dimensions, { key: dim.key, weight: 1 }] });
                    else patch({ dimensions: config.dimensions.filter((d) => d.key !== dim.key) });
                  }}
                />
                <span className="text-[13px] text-[var(--inner-ink)]">{dim.label}</span>
              </div>
            );
          })}
        </div>
      </Section>

      <Section title={`Core questions (${config.questionBank.core.length})`}>
        <QuestionListEditor
          questions={config.questionBank.core}
          onChange={(qs) => patch({ questionBank: { ...config.questionBank, core: qs } })}
          dimensionKeys={chosenDimensionKeys}
          adaptivePoolKeys={config.questionBank.adaptivePool.map((q) => q.key)}
          isCore
        />
      </Section>

      <Section title={`Adaptive pool questions (${config.questionBank.adaptivePool.length})`}>
        <QuestionListEditor
          questions={config.questionBank.adaptivePool}
          onChange={(qs) => patch({ questionBank: { ...config.questionBank, adaptivePool: qs } })}
          dimensionKeys={chosenDimensionKeys}
          adaptivePoolKeys={config.questionBank.adaptivePool.map((q) => q.key)}
          isCore={false}
        />
      </Section>

      <Section title={`Adaptive rules (${config.adaptiveRules.length})`}>
        <AdaptiveRulesEditor rules={config.adaptiveRules} onChange={(rules) => patch({ adaptiveRules: rules })} />
      </Section>

      <Section title={`Profiles (${config.profiles.length})`}>
        <ProfileListEditor profiles={config.profiles} onChange={(profiles) => patch({ profiles })} dimensionKeys={chosenDimensionKeys} />
      </Section>

      <Section title={`Report structure (${config.premiumReportStructure.length})`}>
        <ReportStructureEditor sections={config.premiumReportStructure} onChange={(s) => patch({ premiumReportStructure: s })} />
      </Section>

      <Section title={`Recommendations (${config.recommendedNext.length})`}>
        <RecommendationsEditor
          candidates={config.recommendedNext}
          onChange={(r) => patch({ recommendedNext: r })}
          dimensionKeys={chosenDimensionKeys}
          otherAssessmentSlugs={otherAssessmentSlugs}
        />
      </Section>

      <Section title="Pricing">
        <div className="mb-3">
          <label className={label}>Currency</label>
          <select
            className={input}
            value={config.pricing.individual?.currency ?? config.pricing.deep?.currency ?? "EUR"}
            onChange={(e) => {
              const currency = e.target.value;
              patch({
                pricing: {
                  ...config.pricing,
                  ...(config.pricing.individual ? { individual: { ...config.pricing.individual, currency } } : {}),
                  ...(config.pricing.deep ? { deep: { ...config.pricing.deep, currency } } : {}),
                },
              });
            }}
          >
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className={label}>Individual report</label>
            <input
              type="number"
              step="0.01"
              className={input}
              value={(config.pricing.individual?.amountCents ?? 799) / 100}
              onChange={(e) =>
                patch({
                  pricing: {
                    ...config.pricing,
                    individual: {
                      productType: "individual",
                      amountCents: Math.round(Number(e.target.value) * 100),
                      currency: config.pricing.individual?.currency ?? config.pricing.deep?.currency ?? "EUR",
                    },
                  },
                })
              }
            />
          </div>
          <div>
            <label className={label}>Deep report</label>
            <input
              type="number"
              step="0.01"
              className={input}
              value={(config.pricing.deep?.amountCents ?? 1299) / 100}
              onChange={(e) =>
                patch({
                  pricing: {
                    ...config.pricing,
                    deep: {
                      productType: "deep",
                      amountCents: Math.round(Number(e.target.value) * 100),
                      currency: config.pricing.deep?.currency ?? config.pricing.individual?.currency ?? "EUR",
                    },
                  },
                })
              }
            />
          </div>
        </div>
      </Section>
    </div>
  );
}

// --- Dimension contribution / range editors -------------------------------

function ContributionsEditor({
  value,
  onChange,
  dimensionKeys,
}: {
  value: Partial<Record<string, number>>;
  onChange: (v: Partial<Record<string, number>>) => void;
  dimensionKeys: string[];
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {dimensionKeys.map((key) => (
        <label key={key} className="flex items-center gap-1 text-[12px] text-[var(--inner-ink-soft)]">
          {key}
          <input
            type="number"
            step="1"
            min={-3}
            max={3}
            className="w-14 rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-1 py-0.5 text-[12px]"
            value={value[key] ?? 0}
            onChange={(e) => {
              const num = Number(e.target.value);
              const next = { ...value };
              if (num === 0) delete next[key];
              else next[key] = num;
              onChange(next);
            }}
          />
        </label>
      ))}
    </div>
  );
}

function RangeEditor({
  value,
  onChange,
  dimensionKeys,
}: {
  value: Partial<Record<string, [number, number]>>;
  onChange: (v: Partial<Record<string, [number, number]>>) => void;
  dimensionKeys: string[];
}) {
  return (
    <div className="space-y-1.5">
      {dimensionKeys.map((key) => {
        const range = value[key];
        return (
          <div key={key} className="flex items-center gap-2 text-[12px] text-[var(--inner-ink-soft)]">
            <input
              type="checkbox"
              checked={!!range}
              onChange={(e) => {
                const next = { ...value };
                if (e.target.checked) next[key] = [0, 100];
                else delete next[key];
                onChange(next);
              }}
            />
            <span className="w-24">{key}</span>
            {range && (
              <>
                <input
                  type="number"
                  className="w-16 rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-1 py-0.5"
                  value={range[0]}
                  onChange={(e) => onChange({ ...value, [key]: [Number(e.target.value), range[1]] })}
                />
                <span>to</span>
                <input
                  type="number"
                  className="w-16 rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-1 py-0.5"
                  value={range[1]}
                  onChange={(e) => onChange({ ...value, [key]: [range[0], Number(e.target.value)] })}
                />
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

// --- Questions --------------------------------------------------------------

const QUESTION_TYPES: QuestionType[] = ["single_select", "multi_select", "scale", "open_text"];

function QuestionListEditor({
  questions,
  onChange,
  dimensionKeys,
  adaptivePoolKeys,
  isCore,
}: {
  questions: Question[];
  onChange: (qs: Question[]) => void;
  dimensionKeys: string[];
  adaptivePoolKeys: string[];
  isCore: boolean;
}) {
  function update(i: number, patch: Partial<Question>) {
    onChange(questions.map((q, idx) => (idx === i ? { ...q, ...patch } : q)));
  }
  function remove(i: number) {
    onChange(questions.filter((_, idx) => idx !== i));
  }
  function add() {
    onChange([
      ...questions,
      { key: `question_${questions.length + 1}`, type: "single_select", prompt: "", isCore, options: [{ key: "a", label: "Option A", dimensionContributions: {} }] },
    ]);
  }
  function changeType(i: number, type: QuestionType) {
    // Clear fields specific to the previous type so stale data (e.g. leftover
    // options on a scale question) never gets silently persisted.
    const base: Question = {
      key: questions[i].key,
      type,
      prompt: questions[i].prompt,
      isCore,
      sensitive: questions[i].sensitive,
      difficulty: questions[i].difficulty,
    };
    if (type === "single_select" || type === "multi_select") {
      base.options = questions[i].options?.length ? questions[i].options : [{ key: "a", label: "Option A", dimensionContributions: {} }];
    } else if (type === "scale") {
      base.scaleMax = questions[i].scaleMax ?? 5;
      base.scaleDimension = questions[i].scaleDimension;
    } else if (type === "open_text") {
      base.dynamicFollowupCandidates = questions[i].dynamicFollowupCandidates;
    }
    onChange(questions.map((q, idx) => (idx === i ? base : q)));
  }

  return (
    <div className="space-y-4">
      {questions.map((q, i) => (
        <div key={i} className="rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] p-3">
          <div className="mb-2 flex gap-2">
            <input className={input} placeholder="key" value={q.key} onChange={(e) => update(i, { key: e.target.value })} />
            <select className={input} value={q.type} onChange={(e) => changeType(i, e.target.value as QuestionType)}>
              {QUESTION_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <button onClick={() => remove(i)} className={removeBtn}>
              Remove
            </button>
          </div>
          <textarea
            className={`${input} mb-2`}
            rows={2}
            placeholder="Question prompt"
            value={q.prompt}
            onChange={(e) => update(i, { prompt: e.target.value })}
          />

          <div className="mb-2 flex items-center gap-4">
            <label className="flex items-center gap-1 text-[12px] text-[var(--inner-ink-soft)]">
              <input type="checkbox" checked={q.sensitive ?? false} onChange={(e) => update(i, { sensitive: e.target.checked })} />
              Sensitive (offers "Prefer not to answer")
            </label>
            <div className="flex items-center gap-1">
              <label className={label}>Difficulty</label>
              <select
                className={input}
                value={q.difficulty ?? ""}
                onChange={(e) => update(i, { difficulty: (e.target.value || undefined) as Question["difficulty"] })}
              >
                <option value="">—</option>
                <option value="easy">Easy</option>
                <option value="moderate">Moderate</option>
                <option value="deep">Deep</option>
              </select>
            </div>
          </div>

          {(q.type === "single_select" || q.type === "multi_select") && (
            <OptionsEditor
              options={q.options ?? []}
              onChange={(options) => update(i, { options })}
              dimensionKeys={dimensionKeys}
            />
          )}

          {q.type === "scale" && (
            <div className="flex gap-2">
              <div>
                <label className={label}>Scale max</label>
                <input
                  type="number"
                  className={input}
                  value={q.scaleMax ?? 5}
                  onChange={(e) => update(i, { scaleMax: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className={label}>Scale dimension</label>
                <select className={input} value={q.scaleDimension ?? ""} onChange={(e) => update(i, { scaleDimension: e.target.value })}>
                  <option value="">—</option>
                  {dimensionKeys.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {q.type === "open_text" && (
            <div>
              <label className={label}>Dynamic follow-up candidates (Question AI picks at most one)</label>
              <div className="flex flex-wrap gap-2">
                {adaptivePoolKeys
                  .filter((k) => k !== q.key)
                  .map((k) => (
                    <label key={k} className="flex items-center gap-1 text-[12px] text-[var(--inner-ink-soft)]">
                      <input
                        type="checkbox"
                        checked={(q.dynamicFollowupCandidates ?? []).includes(k)}
                        onChange={(e) => {
                          const current = q.dynamicFollowupCandidates ?? [];
                          update(i, {
                            dynamicFollowupCandidates: e.target.checked ? [...current, k] : current.filter((c) => c !== k),
                          });
                        }}
                      />
                      {k}
                    </label>
                  ))}
                {adaptivePoolKeys.length === 0 && <span className="text-[12px] text-[var(--inner-muted)]">Add adaptive pool questions first.</span>}
              </div>
            </div>
          )}
        </div>
      ))}
      <button onClick={add} className={smallBtn}>
        + Add question
      </button>
    </div>
  );
}

function OptionsEditor({
  options,
  onChange,
  dimensionKeys,
}: {
  options: QuestionOption[];
  onChange: (o: QuestionOption[]) => void;
  dimensionKeys: string[];
}) {
  function update(i: number, patch: Partial<QuestionOption>) {
    onChange(options.map((o, idx) => (idx === i ? { ...o, ...patch } : o)));
  }
  function remove(i: number) {
    onChange(options.filter((_, idx) => idx !== i));
  }
  function add() {
    onChange([...options, { key: `option_${options.length + 1}`, label: "", dimensionContributions: {} }]);
  }

  return (
    <div className="space-y-2 rounded-[var(--inner-radius-sm)] bg-[var(--inner-paper)] p-2">
      {options.map((o, i) => (
        <div key={i} className="rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-2">
          <div className="mb-1 flex gap-2">
            <input className={input} placeholder="key" value={o.key} onChange={(e) => update(i, { key: e.target.value })} />
            <input className={input} placeholder="label" value={o.label} onChange={(e) => update(i, { label: e.target.value })} />
            <button onClick={() => remove(i)} className={removeBtn}>
              ✕
            </button>
          </div>
          <ContributionsEditor
            value={o.dimensionContributions}
            onChange={(v) => update(i, { dimensionContributions: v })}
            dimensionKeys={dimensionKeys}
          />
        </div>
      ))}
      <button onClick={add} className={smallBtn}>
        + Add option
      </button>
    </div>
  );
}

// --- Adaptive rules (JSON editor — see component doc comment) --------------

function AdaptiveRulesEditor({ rules, onChange }: { rules: AdaptiveRule[]; onChange: (r: AdaptiveRule[]) => void }) {
  const [text, setText] = useState(JSON.stringify(rules, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  return (
    <div>
      <p className="mb-2 text-[12px] text-[var(--inner-ink-soft)]">
        Raw JSON — array of {"{ key, trigger: { questionKey, op, optionKey?, dimensionKey?, value? }, action: { type, followupQuestionKey? }, priority }"}.
        Edits here apply once valid JSON loses focus.
      </p>
      <textarea
        className={`${input} font-mono text-[12px]`}
        rows={10}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          try {
            const parsed = JSON.parse(text);
            setParseError(null);
            onChange(parsed);
          } catch {
            setParseError("Invalid JSON — not applied.");
          }
        }}
      />
      {parseError && <p className="mt-1 text-[12px] text-[var(--inner-accent)]">{parseError}</p>}
    </div>
  );
}

// --- Profiles ---------------------------------------------------------------

function ProfileListEditor({
  profiles,
  onChange,
  dimensionKeys,
}: {
  profiles: ProfileDefinition[];
  onChange: (p: ProfileDefinition[]) => void;
  dimensionKeys: string[];
}) {
  function update(i: number, patch: Partial<ProfileDefinition>) {
    onChange(profiles.map((p, idx) => (idx === i ? { ...p, ...patch } : p)));
  }
  function remove(i: number) {
    onChange(profiles.filter((_, idx) => idx !== i));
  }
  function add() {
    onChange([...profiles, { key: `profile_${profiles.length + 1}`, name: "", descriptionTemplate: "", matchingRule: { dimensionRanges: {} } }]);
  }

  return (
    <div className="space-y-4">
      {profiles.map((p, i) => (
        <div key={i} className="rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] p-3">
          <div className="mb-2 flex gap-2">
            <input className={input} placeholder="key" value={p.key} onChange={(e) => update(i, { key: e.target.value })} />
            <input className={input} placeholder="Name" value={p.name} onChange={(e) => update(i, { name: e.target.value })} />
            <button onClick={() => remove(i)} className={removeBtn}>
              Remove
            </button>
          </div>
          <textarea
            className={`${input} mb-2`}
            rows={2}
            placeholder="Non-diagnostic, hedged description ('Your responses suggest...')"
            value={p.descriptionTemplate}
            onChange={(e) => update(i, { descriptionTemplate: e.target.value })}
          />
          <label className={label}>Matching ranges (normalized 0-100)</label>
          <RangeEditor
            value={p.matchingRule.dimensionRanges}
            onChange={(dimensionRanges) => update(i, { matchingRule: { dimensionRanges } })}
            dimensionKeys={dimensionKeys}
          />
        </div>
      ))}
      <button onClick={add} className={smallBtn}>
        + Add profile
      </button>
    </div>
  );
}

// --- Report structure ---------------------------------------------------------------

function ReportStructureEditor({ sections, onChange }: { sections: ReportSection[]; onChange: (s: ReportSection[]) => void }) {
  function update(i: number, patch: Partial<ReportSection>) {
    onChange(sections.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  }
  function remove(i: number) {
    onChange(sections.filter((_, idx) => idx !== i));
  }
  function add() {
    onChange([...sections, { key: `section_${sections.length + 1}`, title: "", promptRef: "" }]);
  }

  return (
    <div className="space-y-2">
      {sections.map((s, i) => (
        <div key={i} className="flex gap-2">
          <input className={input} placeholder="key" value={s.key} onChange={(e) => update(i, { key: e.target.value })} />
          <input className={input} placeholder="Title" value={s.title} onChange={(e) => update(i, { title: e.target.value })} />
          <button onClick={() => remove(i)} className={removeBtn}>
            ✕
          </button>
        </div>
      ))}
      <button onClick={add} className={smallBtn}>
        + Add section
      </button>
    </div>
  );
}

// --- Recommendations ---------------------------------------------------------------

function RecommendationsEditor({
  candidates,
  onChange,
  dimensionKeys,
  otherAssessmentSlugs,
}: {
  candidates: RecommendationCandidate[];
  onChange: (c: RecommendationCandidate[]) => void;
  dimensionKeys: string[];
  otherAssessmentSlugs: string[];
}) {
  function update(i: number, patch: Partial<RecommendationCandidate>) {
    onChange(candidates.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  }
  function remove(i: number) {
    onChange(candidates.filter((_, idx) => idx !== i));
  }
  function add() {
    onChange([...candidates, { assessmentSlug: otherAssessmentSlugs[0] ?? "", condition: { dimensionRanges: {} }, weight: 1, bridgeCopy: "" }]);
  }

  return (
    <div className="space-y-4">
      {candidates.map((c, i) => (
        <div key={i} className="rounded-[var(--inner-radius-md)] border border-[var(--inner-line)] p-3">
          <div className="mb-2 flex gap-2">
            <select className={input} value={c.assessmentSlug} onChange={(e) => update(i, { assessmentSlug: e.target.value })}>
              {otherAssessmentSlugs.map((slug) => (
                <option key={slug} value={slug}>
                  {slug}
                </option>
              ))}
            </select>
            <input
              type="number"
              step="0.1"
              className={`${input} w-24`}
              value={c.weight}
              onChange={(e) => update(i, { weight: Number(e.target.value) })}
              placeholder="weight"
            />
            <button onClick={() => remove(i)} className={removeBtn}>
              Remove
            </button>
          </div>
          <textarea
            className={`${input} mb-2`}
            rows={2}
            placeholder="Bridge copy (fallback when AI is unavailable)"
            value={c.bridgeCopy}
            onChange={(e) => update(i, { bridgeCopy: e.target.value })}
          />
          <label className={label}>Trigger condition (normalized 0-100)</label>
          <RangeEditor
            value={c.condition.dimensionRanges}
            onChange={(dimensionRanges) => update(i, { condition: { dimensionRanges } })}
            dimensionKeys={dimensionKeys}
          />
        </div>
      ))}
      <button onClick={add} className={smallBtn}>
        + Add recommendation
      </button>
    </div>
  );
}
