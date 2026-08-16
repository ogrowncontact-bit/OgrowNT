import { NewAssessmentForm } from "@/components/admin/NewAssessmentForm";

export default function NewAssessmentPage() {
  return (
    <div className="max-w-lg">
      <h1 className="font-display mb-6 text-[24px] text-[var(--inner-ink)]">New experience</h1>
      <p className="mb-6 text-[14px] text-[var(--inner-ink-soft)]">
        This creates the basics — you&apos;ll add questions, profiles, and everything else in the builder next.
      </p>
      <NewAssessmentForm />
    </div>
  );
}
