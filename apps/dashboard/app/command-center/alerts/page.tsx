import { cookies } from "next/headers";
import { getAlerts } from "@/lib/api";
import { AlertCenterPanel } from "@/components/AlertCenterPanel";

export const dynamic = "force-dynamic";

export default async function AlertsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const alerts = await getAlerts(token, 100);
  return <AlertCenterPanel alerts={alerts ?? []} />;
}
