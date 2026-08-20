"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const inputClass =
  "w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-paper)] px-3 py-2 text-[13px] text-[var(--inner-ink)]";
const labelClass = "mb-1 block text-[12px] text-[var(--inner-muted)]";
const btnClass = "rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[12px] text-[var(--inner-ink)] disabled:opacity-40";
const btnPrimary = "rounded-[var(--inner-radius-sm)] bg-[var(--inner-ink)] px-3 py-1.5 text-[12px] text-[var(--inner-paper)] disabled:opacity-40";

export interface PromptEditorTemplate {
  id: string;
  assessmentSlug: string;
  assessmentName: string;
  version: number;
  status: "draft" | "testing" | "published" | "archived";
  personaName: string;
  personaFocus: string;
  personaPrompt: string;
  toneWarmth: number;
  toneDirectness: number;
  toneDepth: number;
  toneFormality: number;
}

export function PromptEditor({
  template,
  profiles,
  readOnly,
}: {
  template: PromptEditorTemplate;
  profiles: { key: string; name: string }[];
  readOnly: boolean;
}) {
  const router = useRouter();
  const [personaName, setPersonaName] = useState(template.personaName);
  const [personaFocus, setPersonaFocus] = useState(template.personaFocus);
  const [personaPrompt, setPersonaPrompt] = useState(template.personaPrompt);
  const [toneWarmth, setToneWarmth] = useState(template.toneWarmth);
  const [toneDirectness, setToneDirectness] = useState(template.toneDirectness);
  const [toneDepth, setToneDepth] = useState(template.toneDepth);
  const [toneFormality, setToneFormality] = useState(template.toneFormality);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const editable = !readOnly && (template.status === "draft" || template.status === "testing");

  async function callAction(path: string, method: string, body?: unknown) {
    const res = await fetch(path, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.error ?? "Request failed");
    return data;
  }

  async function handleSave() {
    setBusy("save");
    setError(null);
    setSaved(false);
    try {
      await callAction(`/api/admin/prompts/${template.id}`, "PATCH", { personaName, personaFocus, personaPrompt, toneWarmth, toneDirectness, toneDepth, toneFormality });
      setSaved(true);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  async function handlePublish() {
    if (!window.confirm(`Publish this persona for "${template.assessmentName}"? It will immediately narrate every new report for this assessment.`)) return;
    setBusy("publish");
    setError(null);
    try {
      await callAction(`/api/admin/prompts/${template.id}/publish`, "POST");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  async function handleTesting() {
    setBusy("testing");
    setError(null);
    try {
      await callAction(`/api/admin/prompts/${template.id}/testing`, "POST");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  async function handleDuplicate() {
    setBusy("duplicate");
    setError(null);
    try {
      const data = await callAction(`/api/admin/prompts/${template.id}/duplicate`, "POST");
      router.push(`/admin/ai/prompts/${data.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(null);
    }
  }

  async function handleArchive() {
    if (!window.confirm("Archive this prompt version?")) return;
    setBusy("archive");
    setError(null);
    try {
      await callAction(`/api/admin/prompts/${template.id}/archive`, "POST");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-8">
      <div className="max-w-lg space-y-4">
        <div>
          <label className={labelClass} htmlFor="personaName">
            Persona name
          </label>
          <input id="personaName" value={personaName} onChange={(e) => setPersonaName(e.target.value)} disabled={!editable} className={inputClass} />
        </div>
        <div>
          <label className={labelClass} htmlFor="personaFocus">
            Focus (Layer 2 perspective)
          </label>
          <input id="personaFocus" value={personaFocus} onChange={(e) => setPersonaFocus(e.target.value)} disabled={!editable} className={inputClass} />
        </div>
        <div>
          <label className={labelClass} htmlFor="personaPrompt">
            Persona voice instructions
          </label>
          <textarea
            id="personaPrompt"
            value={personaPrompt}
            onChange={(e) => setPersonaPrompt(e.target.value)}
            disabled={!editable}
            rows={6}
            className={inputClass}
          />
        </div>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {(
            [
              ["Warmth", toneWarmth, setToneWarmth],
              ["Directness", toneDirectness, setToneDirectness],
              ["Depth", toneDepth, setToneDepth],
              ["Formality", toneFormality, setToneFormality],
            ] as const
          ).map(([label, value, setter]) => (
            <div key={label}>
              <label className={labelClass}>
                {label} ({value.toFixed(2)})
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={value}
                onChange={(e) => setter(Number(e.target.value))}
                disabled={!editable}
                className="w-full"
              />
            </div>
          ))}
        </div>

        {editable && (
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={handleSave} disabled={busy !== null} className={btnPrimary}>
              {busy === "save" ? "Saving..." : "Save draft"}
            </button>
            {template.status === "draft" && (
              <button onClick={handleTesting} disabled={busy !== null} className={btnClass}>
                Mark as testing
              </button>
            )}
            <button onClick={handlePublish} disabled={busy !== null} className={btnClass}>
              Publish
            </button>
            {saved && <span className="text-[12px] text-[var(--inner-ink-soft)]">Saved.</span>}
          </div>
        )}

        {!readOnly && (
          <div className="flex flex-wrap items-center gap-2 border-t border-[var(--inner-line)] pt-4">
            <button onClick={handleDuplicate} disabled={busy !== null} className={btnClass}>
              Duplicate as new draft
            </button>
            {template.status !== "published" && (
              <button onClick={handleArchive} disabled={busy !== null} className={btnClass}>
                Archive
              </button>
            )}
          </div>
        )}

        {error && (
          <p role="alert" className="text-[12px] text-[var(--inner-accent)]">
            {error}
          </p>
        )}
        {!editable && !readOnly && (
          <p className="text-[12px] text-[var(--inner-muted)]">
            {template.status === "published"
              ? "This is the live, published version — it's immutable. Duplicate it to make changes."
              : "This version is archived — it's immutable. Duplicate it to make changes."}
          </p>
        )}
      </div>

      <PromptPlayground templateId={template.id} profiles={profiles} />
    </div>
  );
}

function PromptPlayground({ templateId, profiles }: { templateId: string; profiles: { key: string; name: string }[] }) {
  const [sampleProfileKey, setSampleProfileKey] = useState(profiles[0]?.key ?? "");
  const [sampleThemes, setSampleThemes] = useState("");
  const [language, setLanguage] = useState("en");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [output, setOutput] = useState<any>(null);

  async function handleRun() {
    setRunning(true);
    setError(null);
    setOutput(null);
    try {
      const res = await fetch(`/api/admin/prompts/${templateId}/playground`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sampleProfileKey, sampleThemes, language }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error ?? "Playground run failed");
      setOutput(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="max-w-2xl border-t border-[var(--inner-line)] pt-6">
      <h2 className="font-display mb-2 text-[17px] text-[var(--inner-ink)]">Playground</h2>
      <p className="mb-4 text-[12px] text-[var(--inner-ink-soft)]">
        Runs this exact persona (even if it's still a draft) against synthesized sample evidence built from the
        assessment's own config — never a real user's answers. Shows the real structured output the report pipeline
        would produce. Requires ANTHROPIC_API_KEY to be set; without it you'll see the deterministic fallback, which
        is still useful for checking the fallback copy.
      </p>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div>
          <label className={labelClass} htmlFor="sampleProfile">
            Sample profile
          </label>
          <select id="sampleProfile" value={sampleProfileKey} onChange={(e) => setSampleProfileKey(e.target.value)} className={inputClass}>
            {profiles.map((p) => (
              <option key={p.key} value={p.key}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass} htmlFor="sampleThemes">
            Sample themes (comma-separated, stands in for open answers)
          </label>
          <input id="sampleThemes" value={sampleThemes} onChange={(e) => setSampleThemes(e.target.value)} className={inputClass} placeholder="protects-independence, fears-rejection" />
        </div>
        <div>
          <label className={labelClass} htmlFor="language">
            Language
          </label>
          <select id="language" value={language} onChange={(e) => setLanguage(e.target.value)} className={inputClass}>
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="pt">Portuguese</option>
          </select>
        </div>
        <button onClick={handleRun} disabled={running || !sampleProfileKey} className={btnPrimary}>
          {running ? "Running..." : "Run AI"}
        </button>
      </div>

      {error && (
        <p role="alert" className="mb-3 text-[12px] text-[var(--inner-accent)]">
          {error}
        </p>
      )}

      {output && (
        <div className="space-y-3 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4">
          <p className="text-[12px] text-[var(--inner-muted)]">
            Sample profile: {output.sampleProfileName} · Model: {output.result.modelVersion} · Persona v{output.personaVersion} ({output.personaStatus})
          </p>
          {output.result.sections.map((s: { key: string; title: string; body: string; aiGenerated: boolean }) => (
            <div key={s.key}>
              <p className="text-[12px] font-medium text-[var(--inner-accent)]">
                {s.title} {!s.aiGenerated && <span className="text-[var(--inner-muted)]">(fallback)</span>}
              </p>
              <p className="text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">{s.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
