import { cookies } from "next/headers";
import { getDashboardResearch } from "@/lib/api";
import { AutonomousResearchLab } from "@/components/AutonomousResearchLab";

export const dynamic = "force-dynamic";

export default async function ResearchPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const report = await getDashboardResearch(token);
  return <AutonomousResearchLab report={report} />;
}
