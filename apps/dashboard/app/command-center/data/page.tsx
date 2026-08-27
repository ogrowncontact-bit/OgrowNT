import { cookies } from "next/headers";
import { getMarketOverview } from "@/lib/api";
import { DataFreshnessPanel } from "@/components/DataFreshnessPanel";

export const dynamic = "force-dynamic";

export default async function DataPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const overview = await getMarketOverview(token);
  return <DataFreshnessPanel overview={overview} />;
}
