import { LOVE_DEMO_PERSONAS } from "@/lib/demoPersonas";
import { DemoPersonaPicker } from "@/components/admin/DemoPersonaPicker";

export const dynamic = "force-dynamic";

export default function AdminDemoPage() {
  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">Demo Mode</h1>
      <p className="mb-6 max-w-2xl text-[13px] leading-relaxed text-[var(--inner-ink-soft)]">
        Runs LOVE&apos;s real question engine end to end with a programmatically-selected answer pattern for the persona you
        pick — the same engine, scoring, and AI enrichment a genuine visitor goes through, just answered on their behalf. It
        opens the actual public result page in a new tab so you can inspect exactly what a visitor with that pattern would
        see. This is a dev/founder tool only — it is never reachable from the public site, and Demo Mode purchases still go
        through the existing test-payment banner, never a real charge.
      </p>
      <DemoPersonaPicker personas={LOVE_DEMO_PERSONAS} />
    </div>
  );
}
