"use client";

import { useMemo, useState } from "react";

const inputClass =
  "w-full rounded-[var(--inner-radius-sm)] border border-[var(--inner-line)] bg-[var(--inner-paper)] px-3 py-2 text-[13px] text-[var(--inner-ink)]";
const labelClass = "mb-1 block text-[12px] text-[var(--inner-muted)]";

export function UtmBuilder({ siteUrl, landingSlugs }: { siteUrl: string; landingSlugs: string[] }) {
  const [landing, setLanding] = useState("");
  const [source, setSource] = useState("");
  const [medium, setMedium] = useState("");
  const [campaign, setCampaign] = useState("");
  const [content, setContent] = useState("");
  const [term, setTerm] = useState("");
  const [copied, setCopied] = useState(false);

  const url = useMemo(() => {
    const base = landing ? `${siteUrl}/${landing}` : siteUrl;
    const params = new URLSearchParams();
    if (source) params.set("utm_source", source);
    if (medium) params.set("utm_medium", medium);
    if (campaign) params.set("utm_campaign", campaign);
    if (content) params.set("utm_content", content);
    if (term) params.set("utm_term", term);
    const query = params.toString();
    return query ? `${base}?${query}` : base;
  }, [siteUrl, landing, source, medium, campaign, content, term]);

  async function copy() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5">
      <p className="font-display mb-4 text-[16px] text-[var(--inner-ink)]">UTM Builder</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className={labelClass}>Landing</label>
          <select value={landing} onChange={(e) => setLanding(e.target.value)} className={inputClass}>
            <option value="">Homepage (/)</option>
            {landingSlugs.map((s) => (
              <option key={s} value={s}>
                /{s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>Source</label>
          <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="instagram" className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Medium</label>
          <input value={medium} onChange={(e) => setMedium(e.target.value)} placeholder="paid_social" className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Campaign</label>
          <input value={campaign} onChange={(e) => setCampaign(e.target.value)} placeholder="spring_launch" className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Content</label>
          <input value={content} onChange={(e) => setContent(e.target.value)} placeholder="carousel_1" className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Term</label>
          <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="relationship+quiz" className={inputClass} />
        </div>
      </div>

      <div className="mt-4">
        <label className={labelClass}>Generated URL</label>
        <div className="flex gap-2">
          <input readOnly value={url} className={`${inputClass} truncate`} />
          <button
            onClick={copy}
            className="shrink-0 rounded-[var(--inner-radius-sm)] bg-[var(--inner-ink)] px-3 py-2 text-[12px] text-[var(--inner-paper)]"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>
    </div>
  );
}
