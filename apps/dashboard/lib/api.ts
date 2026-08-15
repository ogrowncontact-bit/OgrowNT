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
export type Position = {
  id: number;
  asset_symbol: string;
  strategy_code: string;
  direction: "long" | "short";
  entry_price: number;
  current_stop: number;
  target_price: number | null;
  size: number;
  opened_at: string;
  closed_at: string | null;
  status: "open" | "closed";
  unrealized_pnl: number | null;
  realized_pnl: number | null;
  exit_price: number | null;
  exit_reason: string | null;
};
export type Trade = {
  id: number;
  position_id: number;
  asset_symbol: string;
  strategy_code: string;
  direction: "long" | "short";
  pnl: number;
  r_multiple: number | null;
  outcome: "win" | "loss" | "breakeven";
  is_paper: boolean;
  closed_at: string;
};
export type NewsImpact = {
  asset_symbol: string;
  direction: "bullish" | "bearish" | "neutral";
  impact: "low" | "medium" | "high";
  confidence: number;
  horizon_hours: number;
  rationale: string;
};
export type NewsEvent = {
  id: number;
  source: string;
  published_at: string;
  headline: string;
  category: string | null;
  impacts: NewsImpact[];
};
export type StrategyLearning = {
  strategy_id: number;
  strategy_code: string;
  lifecycle_stage: string;
  as_of: string | null;
  window_trades: number;
  total_trades: number;
  win_rate: number | null;
  profit_factor: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  expectancy: number | null;
  best_regime: string | null;
  worst_regime: string | null;
  health_score: number | null;
};
export type TradeJournalEntry = {
  trade_id: number;
  asset_symbol: string;
  strategy_code: string;
  expected_outcome: string;
  actual_outcome: string;
  hypothesis: string | null;
  root_cause: string | null;
  created_at: string;
};
export type LearnedRule = {
  id: number;
  scope: string;
  condition: Record<string, unknown>;
  conclusion: string;
  confidence: number;
  sample_size: number;
  status: "candidate" | "validated" | "rejected" | "retired";
  created_at: string;
  validated_at: string | null;
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
export const getPositions = (statusFilter: "open" | "closed" = "open") =>
  apiFetch<Position[]>(`/api/positions?status_filter=${statusFilter}`);
export const getOpportunities = (limit = 10) => apiFetch<Opportunity[]>(`/api/opportunities?limit=${limit}`);
export const getRegimes = () => apiFetch<Regime[]>("/api/regime");
export const getTrades = (limit = 10) => apiFetch<Trade[]>(`/api/trades?limit=${limit}`);
export const getNews = (limit = 10) => apiFetch<NewsEvent[]>(`/api/news?limit=${limit}`);
export const getStrategyLearning = () => apiFetch<StrategyLearning[]>("/api/learning/strategy-performance");
export const getTradeJournal = (limit = 10) => apiFetch<TradeJournalEntry[]>(`/api/learning/trade-journal?limit=${limit}`);
export const getLearnedRules = (limit = 10) => apiFetch<LearnedRule[]>(`/api/research/rules?limit=${limit}`);

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
