import { cookies } from "next/headers";
import { getBrokerHealth, getBrokers, getDashboardExecution } from "@/lib/api";
import { ExecutionCommandCenter } from "@/components/ExecutionCommandCenter";

export const dynamic = "force-dynamic";

export default async function ExecutionPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [brokers, data] = await Promise.all([getBrokers(token), getDashboardExecution(token)]);
  const brokerHealthEntries = await Promise.all(
    (brokers ?? []).map(async (b) => [b.id, await getBrokerHealth(token, b.id)] as const)
  );
  const brokerHealth = Object.fromEntries(brokerHealthEntries);

  return (
    <ExecutionCommandCenter
      brokers={brokers}
      brokerHealth={brokerHealth}
      accounts={data?.accounts ?? null}
      executions={data?.executions ?? null}
      reconciliationRuns={data?.reconciliation ?? null}
      executionHealth={data?.health ?? null}
    />
  );
}
