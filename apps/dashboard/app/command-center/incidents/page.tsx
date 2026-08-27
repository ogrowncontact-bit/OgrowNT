import { cookies } from "next/headers";
import { getIncidents } from "@/lib/api";
import { IncidentFeed } from "@/components/IncidentFeed";

export const dynamic = "force-dynamic";

export default async function IncidentsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const incidents = await getIncidents(token);
  return <IncidentFeed incidents={incidents ?? []} />;
}
