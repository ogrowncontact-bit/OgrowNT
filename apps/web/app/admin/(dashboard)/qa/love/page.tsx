import { getLatestLoveQaRun } from "@/lib/admin/qaReader";
import { QaRunTrigger } from "@/components/admin/QaRunTrigger";

export const dynamic = "force-dynamic";

function formatDate(d: Date) {
  return new Intl.DateTimeFormat("en-IE", { dateStyle: "medium", timeStyle: "short" }).format(d);
}

const card = "rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5";
const sectionTitle = "font-display mb-3 text-[16px] text-[var(--inner-ink)]";

/**
 * FASE 31 §QUALITY DASHBOARD — /admin/qa/love. Shows the latest 100-persona
 * simulation run: profile distribution (flagging >25%/<1%), dimension score
 * ranges, tension/contradiction firing rates, per-question ask/option
 * stats, and structurally-detected redundant questions. Every number here
 * comes from a real run of the actual engine (lib/qa/runLoveQaSimulation.ts)
 * — nothing on this page is invented. AI-dependent quality checks (safety
 * language, generic-content score, report similarity, personalization,
 * prompt-injection handling, multi-language output) are explicitly called
 * out as not evaluated when no ANTHROPIC_API_KEY is configured, rather than
 * shown as a fabricated pass.
 */
export default async function AdminQaLovePage() {
  const run = await getLatestLoveQaRun();

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-[24px] text-[var(--inner-ink)]">LOVE Quality Dashboard</h1>
          <p className="mt-1 text-[13px] text-[var(--inner-ink-soft)]">
            {run ? `Last run: ${formatDate(run.createdAt)} — ${run.result.personaCount} personas` : "No simulation has been run yet."}
          </p>
        </div>
        <QaRunTrigger />
      </div>

      {!run ? (
        <div className={card}>
          <p className="text-[14px] text-[var(--inner-ink-soft)]">
            Run a simulation to see profile distribution, question performance, and adaptive engine behavior across
            100 varied synthetic personas.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          <div className={card}>
            <p className={sectionTitle}>AI-dependent checks</p>
            {run.result.aiWasEnabled ? (
              <p className="text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">
                AI was enabled for this run. Safety-language scanning, generic-content scoring, report similarity, and
                personalization evidence are not yet computed automatically here — inspect individual generated
                reports via /admin/reports/preview for now.
              </p>
            ) : (
              <p className="text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">
                <strong>Not evaluated.</strong> No ANTHROPIC_API_KEY is configured in this environment, so every AI
                call fell back to the same static template content regardless of persona — comparing that output
                would only measure the fallback template, not real AI behavior. Safety-claim scanning, generic-content
                scoring, report semantic similarity, personalization evidence, prompt-injection handling, and
                multi-language output quality all require a real AI key to test meaningfully.
              </p>
            )}
          </div>

          <div className={card}>
            <p className={sectionTitle}>Profile distribution ({run.result.personaCount} personas)</p>
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                  <th className="py-2 font-medium">Profile</th>
                  <th className="py-2 font-medium">Count</th>
                  <th className="py-2 font-medium">Share</th>
                  <th className="py-2 font-medium">Flag</th>
                </tr>
              </thead>
              <tbody>
                {run.result.profileDistribution.map((p) => (
                  <tr key={p.profileKey} className="border-b border-[var(--inner-line)] last:border-0">
                    <td className="py-2 font-medium text-[var(--inner-ink)]">{p.profileName}</td>
                    <td className="py-2 text-[var(--inner-ink-soft)]">{p.count}</td>
                    <td className="py-2 text-[var(--inner-ink-soft)]">{p.pct}%</td>
                    <td className="py-2">
                      {p.flag === "too_common" && <span className="text-[var(--inner-accent)]">Reached too easily (&gt;25%)</span>}
                      {p.flag === "too_rare" && <span className="text-[var(--inner-accent)]">Rarely/never reached (&lt;1%)</span>}
                      {!p.flag && <span className="text-[var(--inner-muted)]">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={card}>
            <p className={sectionTitle}>Dimension score ranges (0–100, across all completions)</p>
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                  <th className="py-2 font-medium">Dimension</th>
                  <th className="py-2 font-medium">Min</th>
                  <th className="py-2 font-medium">Avg</th>
                  <th className="py-2 font-medium">Max</th>
                </tr>
              </thead>
              <tbody>
                {run.result.dimensionStats.map((d) => (
                  <tr key={d.key} className="border-b border-[var(--inner-line)] last:border-0">
                    <td className="py-2 font-medium text-[var(--inner-ink)]">{d.label}</td>
                    <td className="py-2 text-[var(--inner-ink-soft)]">{d.min}</td>
                    <td className="py-2 text-[var(--inner-ink-soft)]">{d.avg}</td>
                    <td className="py-2 text-[var(--inner-ink-soft)]">{d.max}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-[12px] text-[var(--inner-muted)]">
              A dimension whose min and max never move far from 50 across 100 varied personas suggests the question
              bank isn&apos;t differentiating on it.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <div className={card}>
              <p className={sectionTitle}>Tensions fired</p>
              {run.result.tensionFiringRates.length === 0 ? (
                <p className="text-[13px] text-[var(--inner-muted)]">No tensions fired across this run.</p>
              ) : (
                <ul className="space-y-2 text-[13px]">
                  {run.result.tensionFiringRates.map((t) => (
                    <li key={t.key} className="flex items-center justify-between">
                      <span className="text-[var(--inner-ink-soft)]">{t.label}</span>
                      <span className="font-medium text-[var(--inner-ink)]">
                        {t.firedCount} ({t.pct}%)
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className={card}>
              <p className={sectionTitle}>Contradictions detected</p>
              <p className="mb-3 text-[12px] text-[var(--inner-muted)]">
                Read these rates as an upper bound, not a real-user estimate: for dimensions a persona doesn&apos;t
                deliberately target, the simulation&apos;s own answer-selection deliberately alternates direction to
                stay near the middle — the same alternation the contradiction detector is built to notice. A real
                visitor answering from genuine preference, not a balance-seeking algorithm, would likely trigger this
                less often.
              </p>
              {run.result.contradictionFiringRates.length === 0 ? (
                <p className="text-[13px] text-[var(--inner-muted)]">No contradictions detected across this run.</p>
              ) : (
                <ul className="space-y-2 text-[13px]">
                  {run.result.contradictionFiringRates.map((c) => (
                    <li key={c.key} className="flex items-center justify-between">
                      <span className="text-[var(--inner-ink-soft)]">{c.label}</span>
                      <span className="font-medium text-[var(--inner-ink)]">
                        {c.firedCount} ({c.pct}%)
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className={card}>
            <p className={sectionTitle}>Question performance ({run.result.questionStats.length} questions used)</p>
            <p className="mb-3 text-[12px] text-[var(--inner-muted)]">
              Average {run.result.averageQuestionsPerSession} questions per completed session. Core questions are
              asked every time by design; adaptive-pool questions below 100% only fire for personas whose answers
              trigger them.
            </p>
            <div className="max-h-[480px] overflow-y-auto">
              <table className="w-full text-left text-[13px]">
                <thead className="sticky top-0 bg-[var(--inner-card)]">
                  <tr className="border-b border-[var(--inner-line)] text-[var(--inner-muted)]">
                    <th className="py-2 font-medium">Question</th>
                    <th className="py-2 font-medium">Type</th>
                    <th className="py-2 font-medium">Core</th>
                    <th className="py-2 font-medium">Asked</th>
                    <th className="py-2 font-medium">Top answer</th>
                  </tr>
                </thead>
                <tbody>
                  {run.result.questionStats.map((q) => (
                    <tr key={q.key} className="border-b border-[var(--inner-line)] last:border-0 align-top">
                      <td className="max-w-[280px] py-2 text-[var(--inner-ink-soft)]">{q.prompt}</td>
                      <td className="py-2 text-[var(--inner-ink-soft)]">{q.type}</td>
                      <td className="py-2 text-[var(--inner-ink-soft)]">{q.isCore ? "Yes" : "No"}</td>
                      <td className="py-2 text-[var(--inner-ink-soft)]">
                        {q.timesAsked} ({q.askedPct}%)
                      </td>
                      <td className="py-2 text-[var(--inner-ink-soft)]">
                        {q.optionDistribution && q.optionDistribution.length > 0
                          ? `${q.optionDistribution[0].label} (${q.optionDistribution[0].pct}%)`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className={card}>
            <p className={sectionTitle}>Structurally redundant question pairs</p>
            {run.result.redundantQuestionPairs.length === 0 ? (
              <p className="text-[13px] text-[var(--inner-ink-soft)]">
                None found — no two option-based questions share the exact same set of scored dimensions.
              </p>
            ) : (
              <ul className="space-y-3 text-[13px]">
                {run.result.redundantQuestionPairs.map((pair) => (
                  <li key={`${pair.a}-${pair.b}`} className="rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] p-3">
                    <p className="text-[var(--inner-ink)]">
                      &quot;{pair.aPrompt}&quot; and &quot;{pair.bPrompt}&quot;
                    </p>
                    <p className="mt-1 text-[12px] text-[var(--inner-muted)]">Both only touch: {pair.sharedDimensions.join(", ")}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
