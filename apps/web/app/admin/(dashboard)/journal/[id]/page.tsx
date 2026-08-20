import { notFound } from "next/navigation";
import { getJournalPostById } from "@/lib/admin/journalReader";
import { JournalPostEditor } from "@/components/admin/JournalPostEditor";

export default async function JournalPostEditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const post = await getJournalPostById(id);
  if (!post) notFound();

  return <JournalPostEditor post={post} />;
}
