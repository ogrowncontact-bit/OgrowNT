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
export type Strategy = {
  id: number;
  code: string;
  name: string;
  family: string;
  version: string;
  lifecycle_stage: string;
};
export type DataSource = { provider: string; is_live: boolean };
export type MarketAssetOverview = {
  symbol: string;
  asset_class: string;
  price: number | null;
  pct_change: number | null;
  volatility: number | null;
  volume: number | null;
  trend: string | null;
  data_quality_score: number | null;
  data_quality_status: string | null;
  last_update: string | null;
};
export type MarketOverview = { data_source: DataSource; assets: MarketAssetOverview[] };
export type MarketEvent = {
  id: number;
  asset_symbol: string;
  event_type: string;
  timeframe: string;
  severity: string;
  price: number | null;
  volume: number | null;
  confidence: number;
  meta: Record<string, unknown>;
  ts: string;
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
export type BacktestSummary = {
  id: number;
  strategy_code: string;
  asset_symbol: string;
  timeframe: string;
  kind: string;
  group_label: string | null;
  window_index: number | null;
  total_windows: number | null;
  start_ts: string;
  end_ts: string;
  initial_capital: number;
  net_return: number | null;
  cagr_like_return: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
  avg_trade: number | null;
  expectancy: number | null;
  num_trades: number;
  sharpe_like: number | null;
  created_at: string;
};
export type PromotionCheck = {
  strategy_id: number;
  eligible: boolean;
  current_stage: string;
  next_stage: string | null;
  reasons: string[];
  criteria: Record<string, unknown>;
  actual: Record<string, unknown>;
};
export type SystemAlert = {
  id: number;
  ts: string;
  severity: "info" | "warning" | "critical";
  category: string;
  message: string;
  meta: Record<string, unknown>;
  acknowledged: boolean;
  delivered_at: string | null;
};
export type EquityPoint = { ts: string; equity: number; drawdown_pct: number };
export type TradeStats = {
  total_trades: number;
  win_rate: number | null;
  expectancy: number | null;
  profit_factor: number | null;
  avg_pnl: number | null;
};
export type DrawdownStats = {
  current_drawdown_pct: number | null;
  max_drawdown_pct: number | null;
  peak_equity: number | null;
};
export type PatternLeaderboardEntry = {
  pattern_type: string;
  regime: string;
  sample_size: number;
  win_rate: number | null;
  expectancy: number | null;
};
export type AnalyticsOverview = {
  equity_curve: EquityPoint[];
  trade_stats: TradeStats;
  drawdown: DrawdownStats;
  tier_distribution: Record<string, number>;
  pattern_leaderboard: PatternLeaderboardEntry[];
  regime_distribution: Record<string, number>;
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

// getHealth is the one deliberately public read (docs/blueprint/03-api-spec.md
// exempts /api/system/health, same as /api/auth/login) — every other read
// below requires the admin's Bearer token, same as every mutating endpoint.
export const getHealth = () => apiFetch<HealthResponse>("/api/system/health");
export const getSystemStatus = (token: string) => apiFetch<SystemStatus>("/api/system/status", token);
export const getPortfolio = (token: string) => apiFetch<Portfolio>("/api/portfolio", token);
export const getAssets = (token: string) => apiFetch<Asset[]>("/api/assets", token);
export const getStrategies = (token: string) => apiFetch<Strategy[]>("/api/strategies", token);
export const getMarketOverview = (token: string) => apiFetch<MarketOverview>("/api/market/overview", token);
export const getMarketEvents = (token: string, limit = 10) => apiFetch<MarketEvent[]>(`/api/market/events?limit=${limit}`, token);
export const getPositions = (token: string, statusFilter: "open" | "closed" = "open") =>
  apiFetch<Position[]>(`/api/positions?status_filter=${statusFilter}`, token);
export const getOpportunities = (token: string, limit = 10) => apiFetch<Opportunity[]>(`/api/opportunities?limit=${limit}`, token);
export const getRegimes = (token: string) => apiFetch<Regime[]>("/api/regime", token);
export const getTrades = (token: string, limit = 10) => apiFetch<Trade[]>(`/api/trades?limit=${limit}`, token);
export const getNews = (token: string, limit = 10) => apiFetch<NewsEvent[]>(`/api/news?limit=${limit}`, token);
export const getStrategyLearning = (token: string) => apiFetch<StrategyLearning[]>("/api/learning/strategy-performance", token);
export const getTradeJournal = (token: string, limit = 10) =>
  apiFetch<TradeJournalEntry[]>(`/api/learning/trade-journal?limit=${limit}`, token);
export const getLearnedRules = (token: string, limit = 10) => apiFetch<LearnedRule[]>(`/api/research/rules?limit=${limit}`, token);
export const getBacktests = (token: string, limit = 10) => apiFetch<BacktestSummary[]>(`/api/backtests?limit=${limit}`, token);
export const getPromotionCheck = (token: string, strategyId: number) =>
  apiFetch<PromotionCheck>(`/api/strategies/${strategyId}/promotion-check`, token);
export const getAlerts = (token: string, limit = 10) => apiFetch<SystemAlert[]>(`/api/alerts?limit=${limit}`, token);
export const getAnalyticsOverview = (token: string) => apiFetch<AnalyticsOverview>("/api/analytics/overview", token);

export async function setKillSwitch(token: string, action: "trigger" | "release") {
  const path = action === "trigger" ? "/api/system/kill-switch" : "/api/system/kill-switch/release";
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return (await res.json()) as SystemStatus;
}

export type RunBacktestPayload = {
  strategy_id: number;
  asset_id: number;
  timeframe: string;
  start_ts: string;
  end_ts: string;
  initial_capital: number;
};

export async function runBacktest(token: string, payload: RunBacktestPayload) {
  const res = await fetch(`${API_URL}/api/backtests`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false as const, detail: body?.detail ?? `Backtest failed (${res.status})` };
  return { ok: true as const, result: body as BacktestSummary };
}

export async function strategyAction(token: string, strategyId: number, action: "promote" | "restore") {
  const res = await fetch(`${API_URL}/api/strategies/${strategyId}/${action}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false as const, detail: body?.detail ?? `${action} failed (${res.status})` };
  return { ok: true as const, result: body as Strategy };
}

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
