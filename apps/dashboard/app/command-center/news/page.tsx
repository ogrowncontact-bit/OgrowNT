import { cookies } from "next/headers";
import { getDashboardNews, getHealth } from "@/lib/api";
import { NewsIntelligenceCenter } from "@/components/NewsIntelligenceCenter";

export const dynamic = "force-dynamic";

export default async function NewsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";
  const [data, health] = await Promise.all([getDashboardNews(token), getHealth()]);

  return (
    <NewsIntelligenceCenter
      news={data?.news ?? []}
      macroEvents={data?.macro_events ?? []}
      newsRisk={data?.risk ?? null}
      aiServicesConfigured={health?.components.find((c) => c.name === "ai_services")?.status !== "yellow"}
    />
  );
}
