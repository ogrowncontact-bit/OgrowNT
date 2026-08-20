import { NewJournalPostForm } from "@/components/admin/NewJournalPostForm";

export default function NewJournalPostPage() {
  return (
    <div className="max-w-lg">
      <h1 className="font-display mb-6 text-[24px] text-[var(--inner-ink)]">New journal post</h1>
      <NewJournalPostForm />
    </div>
  );
}
