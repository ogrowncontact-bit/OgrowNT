const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ComponentHealth = { name: string; status: string; detail: string | null };
export type HealthResponse = { overall: string; components: ComponentHealth[] };
export type SystemStatus = {
  safety_belt_level: string;
  trading_enabled: boolean;
  updated_at: string;
  updated_reason: string | null;
};
export type Portfolio = {
  equity: number;
  cash: number;
  exposure_pct: number;
  daily_pnl: number;
  drawdown_pct: number;
  safety_belt_level: string;
  as_of: string;
};
export type Asset = {
  id: number;
  symbol: string;
  asset_class: string;
  exchange: string | null;
  is_active: boolean;
};
export type Opportunity = {
  signal_id: number;
  asset_symbol: string;
  strategy_code: string;
  strategy_name: string;
  direction: "long" | "short";
  entry_price: number;
  stop_price: number;
  target_price: number | null;
  risk_reward: number;
  regime: string;
  final_score: number;
  tier: string;
  ts: string;
};
export type Regime = {
  asset_symbol: string;
  timeframe: string;
  ts: string;
  regime: string;
  confidence: number;
  features: Record<string, unknown>;
};

async function apiFetch<T>(path: string, token?: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    // Backend unreachable — the caller renders this as DATA_UNAVAILABLE /
    // DEGRADED rather than throwing, per docs/blueprint/08-risk-engine.md
    // §Failure Mode ("preferir não operar a operar com dados incompletos").
    return null;
  }
}

export const getHealth = () => apiFetch<HealthResponse>("/api/system/health");
export const getSystemStatus = (token: string) => apiFetch<SystemStatus>("/api/system/status", token);
export const getPortfolio = () => apiFetch<Portfolio>("/api/portfolio");
export const getAssets = () => apiFetch<Asset[]>("/api/assets");
export const getPositions = () => apiFetch<unknown[]>("/api/positions");
export const getOpportunities = (limit = 10) => apiFetch<Opportunity[]>(`/api/opportunities?limit=${limit}`);
export const getRegimes = () => apiFetch<Regime[]>("/api/regime");

export async function login(email: string, password: string) {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });
  if (!res.ok) return null;
  return (await res.json()) as { access_token: string; expires_at: string };
}
