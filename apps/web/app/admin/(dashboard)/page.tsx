import Link from "next/link";

export default function AdminHomePage() {
  return (
    <div>
      <h1 className="font-display mb-6 text-[24px] text-[var(--inner-ink)]">Overview</h1>
      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          href="/admin/assessments"
          className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5 hover:border-[var(--inner-accent-soft)]"
        >
          <h2 className="font-display text-[17px] text-[var(--inner-ink)]">Assessments</h2>
          <p className="mt-2 text-[14px] text-[var(--inner-ink-soft)]">
            Create, edit, and publish INNER experiences without a deploy.
          </p>
        </Link>
        <Link
          href="/admin/analytics"
          className="rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-5 hover:border-[var(--inner-accent-soft)]"
        >
          <h2 className="font-display text-[17px] text-[var(--inner-ink)]">Analytics</h2>
          <p className="mt-2 text-[14px] text-[var(--inner-ink-soft)]">
            Funnel conversion, purchases, and marketing consent — per assessment.
          </p>
        </Link>
      </div>
    </div>
  );
}
