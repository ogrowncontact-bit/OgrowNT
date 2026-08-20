"use client";

import { useState } from "react";
import type { ReportDocument } from "@inner/ai";
import { ReportView } from "@/components/ReportView";

const inputClass =
  "w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-paper)] px-3 py-2 text-[13px] text-[var(--inner-ink)]";
const labelClass = "mb-1 block text-[12px] text-[var(--inner-muted)]";
const btnPrimary = "rounded-[var(--inner-radius-sm)] bg-[var(--inner-ink)] px-3 py-1.5 text-[12px] text-[var(--inner-paper)] disabled:opacity-40";
const btnClass = "rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] px-3 py-1.5 text-[12px] text-[var(--inner-ink)] disabled:opacity-40";

interface AssessmentOption {
  slug: string;
  name: string;
  profiles: { key: string; name: string }[];
}

export function ReportPreviewPanel({ assessments }: { assessments: AssessmentOption[] }) {
  const [slug, setSlug] = useState(assessments[0]?.slug ?? "");
  const [profileKey, setProfileKey] = useState(assessments[0]?.profiles[0]?.key ?? "");
  const [language, setLanguage] = useState("en");
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [document, setDocument] = useState<{ document: ReportDocument; assessmentLabel: string } | null>(null);

  const selected = assessments.find((a) => a.slug === slug);

  function handleSlugChange(newSlug: string) {
    setSlug(newSlug);
    const next = assessments.find((a) => a.slug === newSlug);
    setProfileKey(next?.profiles[0]?.key ?? "");
  }

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setDocument(null);
    try {
      const res = await fetch("/api/admin/reports/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assessmentSlug: slug, sampleProfileKey: profileKey, language }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error ?? "Preview failed");
      setDocument(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadPdf() {
    setPdfLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/reports/preview/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assessmentSlug: slug, sampleProfileKey: profileKey, language }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.error ?? "PDF preview failed");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setPdfLoading(false);
    }
  }

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-end gap-3">
        <div>
          <label className={labelClass} htmlFor="previewAssessment">
            Assessment
          </label>
          <select id="previewAssessment" value={slug} onChange={(e) => handleSlugChange(e.target.value)} className={inputClass}>
            {assessments.map((a) => (
              <option key={a.slug} value={a.slug}>
                {a.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass} htmlFor="previewProfile">
            Sample profile
          </label>
          <select id="previewProfile" value={profileKey} onChange={(e) => setProfileKey(e.target.value)} className={inputClass}>
            {selected?.profiles.map((p) => (
              <option key={p.key} value={p.key}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass} htmlFor="previewLanguage">
            Language
          </label>
          <select id="previewLanguage" value={language} onChange={(e) => setLanguage(e.target.value)} className={inputClass}>
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="pt">Portuguese</option>
          </select>
        </div>
        <button onClick={handleGenerate} disabled={loading || !slug} className={btnPrimary}>
          {loading ? "Generating..." : "Generate preview"}
        </button>
        {document && (
          <button onClick={handleDownloadPdf} disabled={pdfLoading} className={btnClass}>
            {pdfLoading ? "Rendering PDF..." : "Preview PDF"}
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="mb-4 text-[12px] text-[var(--inner-accent)]">
          {error}
        </p>
      )}

      {document && (
        <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-paper)] p-6">
          <ReportView assessmentLabel={document.assessmentLabel} document={document.document} />
        </div>
      )}
    </div>
  );
}
