import { cookies } from "next/headers";
import { getDashboardSystem } from "@/lib/api";
import { SystemHealthPanel } from "@/components/SystemHealthPanel";

export const dynamic = "force-dynamic";

export default async function SystemPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const data = await getDashboardSystem(token);

  if (!data) {
    return <p className="text-xs text-signal-red">System status unavailable — the API may be unreachable.</p>;
  }

  return (
    <SystemHealthPanel
      componentHealth={data.component_health}
      healthScore={data.health_score}
      diagnostic={data.self_diagnostic}
    />
  );
}
