import { cookies } from "next/headers";
import { getBrokers, getHealth, getRiskState, getSystemStatus } from "@/lib/api";
import { SettingsSummary } from "@/components/SettingsSummary";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [riskState, brokers, health, systemStatus] = await Promise.all([
    getRiskState(token),
    getBrokers(token),
    getHealth(),
    getSystemStatus(token),
  ]);

  return <SettingsSummary riskState={riskState} brokers={brokers} health={health} systemStatus={systemStatus} />;
}
