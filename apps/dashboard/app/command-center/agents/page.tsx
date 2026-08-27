import { cookies } from "next/headers";
import { getDashboardAgents } from "@/lib/api";
import { AICommandCenter } from "@/components/AICommandCenter";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const data = await getDashboardAgents(token);

  return (
    <AICommandCenter
      agents={data?.agents ?? []}
      decisions={data?.recent_decisions ?? []}
      contradictions={data?.contradictions ?? []}
    />
  );
}
