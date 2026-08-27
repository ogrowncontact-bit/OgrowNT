import { cookies } from "next/headers";
import { getAuditLog } from "@/lib/api";
import { AuditLogViewer } from "@/components/AuditLogViewer";

export const dynamic = "force-dynamic";

export default async function AuditPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const entries = await getAuditLog(token);
  return <AuditLogViewer entries={entries ?? []} />;
}
