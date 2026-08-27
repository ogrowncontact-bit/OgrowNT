import { cookies } from "next/headers";
import { getDashboardOverview, getGlobalMarketSessions } from "@/lib/api";
import { GlobalStatusBar } from "@/components/GlobalStatusBar";
import { Sidebar } from "@/components/Sidebar";

export const dynamic = "force-dynamic";

export default async function CommandCenterLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ogrownt_token")?.value ?? "";

  const [overview, sessions] = await Promise.all([getDashboardOverview(token), getGlobalMarketSessions(token)]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-base-950 text-ink-100">
      <GlobalStatusBar
        tradingEnabled={overview?.system_state.trading_enabled ?? null}
        tradingPaused={overview?.system_state.trading_paused ?? null}
        safetyBeltLevel={overview?.system_state.safety_belt_level ?? null}
        tradingMode={overview?.system_state.trading_mode ?? null}
        healthScore={overview?.health_score.score ?? null}
        readinessState={overview?.health_score.readiness_state ?? null}
        sessions={sessions?.sessions ?? []}
      />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-4">{children}</main>
      </div>
    </div>
  );
}
