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
  weekly_pnl: number;
  weekly_loss_pct: number;
  monthly_pnl: number;
  monthly_loss_pct: number;
};
export type ExposureItem = { key: string; notional: number; pct_of_equity: number };
export type CorrelationPair = { asset_symbol_a: string; asset_symbol_b: string; correlation: number; ts: string };
export type PortfolioExposure = {
  equity: number;
  by_asset: ExposureItem[];
  by_strategy: ExposureItem[];
  by_direction: ExposureItem[];
  correlations: CorrelationPair[];
};
export type RiskCheckEntry = { check_name: string; passed: boolean; detail: Record<string, unknown> };
export type RiskDecisionEntry = {
  signal_id: number;
  asset_symbol: string;
  strategy_code: string;
  approved: boolean;
  approved_size: number | null;
  reason: string;
  safety_belt_level: string;
  created_at: string;
  checks: RiskCheckEntry[];
  decision: "approved" | "reduced" | "blocked";
  reasons: string[];
  risk_amount: number | null;
  position_size: number | null;
  risk_reward: number | null;
};
export type RiskState = {
  safety_belt_level: string;
  trading_enabled: boolean;
  limits: Record<string, Record<string, number>>;
  recent_decisions: RiskDecisionEntry[];
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
  confidence: number;
  tier: string;
  ts: string;
};
export type EvidenceItem = { kind: "confirm" | "warning"; text: string };
export type OpportunityDetail = Opportunity & {
  regime_confidence: number;
  status: string;
  evidence: EvidenceItem[];
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
  is_direct: boolean;
};
export type NewsEvent = {
  id: number;
  source: string;
  published_at: string;
  headline: string;
  category: string | null;
  impacts: NewsImpact[];
  source_quality_score: number;
  sentiment: "very_bullish" | "bullish" | "neutral" | "bearish" | "very_bearish" | "unknown";
  sentiment_confidence: number;
  importance: "low" | "medium" | "high" | "critical";
  novelty_score: number;
  impact_score: number;
  cluster_id: number | null;
  source_consensus_score: number;
  has_conflicting_sources: boolean;
  entities: { type: string; value: string }[];
};
export type MacroEvent = {
  id: number;
  event: string;
  country: string;
  currency: string | null;
  scheduled_at: string;
  importance: "low" | "medium" | "high" | "critical";
  forecast: number | null;
  previous: number | null;
  actual: number | null;
  surprise: number | null;
  status: "scheduled" | "released";
};
export type NewsRisk = {
  level: "normal" | "elevated" | "high" | "critical";
  size_multiplier: number;
  blocked: boolean;
  reasons: string[];
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
export const getPortfolioExposure = (token: string) => apiFetch<PortfolioExposure>("/api/portfolio/exposure", token);
export const getRiskState = (token: string, limit = 10) => apiFetch<RiskState>(`/api/risk?limit=${limit}`, token);
export const getAssets = (token: string) => apiFetch<Asset[]>("/api/assets", token);
export const getStrategies = (token: string) => apiFetch<Strategy[]>("/api/strategies", token);
export const getMarketOverview = (token: string) => apiFetch<MarketOverview>("/api/market/overview", token);
export const getMarketEvents = (token: string, limit = 10) => apiFetch<MarketEvent[]>(`/api/market/events?limit=${limit}`, token);
export const getPositions = (token: string, statusFilter: "open" | "closed" = "open") =>
  apiFetch<Position[]>(`/api/positions?status_filter=${statusFilter}`, token);
export const getOpportunities = (token: string, limit = 10) => apiFetch<Opportunity[]>(`/api/opportunities?limit=${limit}`, token);
export const getOpportunityDetail = (token: string, signalId: number) =>
  apiFetch<OpportunityDetail>(`/api/opportunities/${signalId}`, token);
export const getRegimes = (token: string) => apiFetch<Regime[]>("/api/regime", token);
export const getTrades = (token: string, limit = 10) => apiFetch<Trade[]>(`/api/trades?limit=${limit}`, token);
export const getNews = (token: string, limit = 10) => apiFetch<NewsEvent[]>(`/api/news?limit=${limit}`, token);
export const getMacroEvents = (token: string) => apiFetch<MacroEvent[]>("/api/macro", token);
export const getNewsRisk = (token: string) => apiFetch<NewsRisk>("/api/news/risk", token);
export const getStrategyLearning = (token: string) => apiFetch<StrategyLearning[]>("/api/learning/strategy-performance", token);
export const getTradeJournal = (token: string, limit = 10) =>
  apiFetch<TradeJournalEntry[]>(`/api/learning/trade-journal?limit=${limit}`, token);
export const getLearnedRules = (token: string, limit = 10) => apiFetch<LearnedRule[]>(`/api/research/rules?limit=${limit}`, token);
export const getBacktests = (token: string, limit = 10) => apiFetch<BacktestSummary[]>(`/api/backtests?limit=${limit}`, token);
export const getPromotionCheck = (token: string, strategyId: number) =>
  apiFetch<PromotionCheck>(`/api/strategies/${strategyId}/promotion-check`, token);
export const getAlerts = (token: string, limit = 10) => apiFetch<SystemAlert[]>(`/api/alerts?limit=${limit}`, token);
export const getAnalyticsOverview = (token: string) => apiFetch<AnalyticsOverview>("/api/analytics/overview", token);

// --- "PROMPT 8" Autonomous Trading Center --------------------------------

export type AutonomousStatus = {
  status: string;
  trading_mode: string;
  trading_enabled: boolean;
  trading_paused: boolean;
  paused_reason: string | null;
  safety_belt_level: string;
  worker_alive: boolean;
  worker_last_heartbeat: string | null;
  open_positions_count: number;
  worker_restart_count: number;
};
export type TradingEvent = {
  id: number;
  ts: string;
  event_type: string;
  entity_type: string | null;
  entity_id: number | null;
  payload: Record<string, unknown>;
};
export type ManualActionEntry = {
  id: number;
  ts: string;
  actor: string;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  reason: string | null;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
};
export type TradingPerformance = {
  trades_today: number;
  wins_today: number;
  losses_today: number;
  win_rate_today: number | null;
  daily_pnl: number;
  open_positions_count: number;
  exposure_pct: number;
  drawdown_pct: number;
  safety_belt_level: string;
  autonomous_status: string;
};

export const getAutonomousStatus = (token: string) => apiFetch<AutonomousStatus>("/api/trading/status", token);
export const getActivityFeed = (token: string, limit = 30) => apiFetch<TradingEvent[]>(`/api/trading/activity?limit=${limit}`, token);
export const getManualActions = (token: string, limit = 20) => apiFetch<ManualActionEntry[]>(`/api/trading/manual-actions?limit=${limit}`, token);
export const getTradingPerformance = (token: string) => apiFetch<TradingPerformance>("/api/trading/performance", token);

// --- "PROMPT 9" AI Command Center -----------------------------------------

export type AgentReliability = {
  as_of: string;
  sample_size: number;
  correct_count: number;
  accuracy: number | null;
  avg_confidence_when_correct: number | null;
  avg_confidence_when_incorrect: number | null;
  overconfidence_gap: number | null;
  reliability_score: number | null;
};
export type Agent = {
  code: string;
  name: string;
  directional: boolean;
  version: string;
  status: string;
  quarantined_at: string | null;
  quarantine_reason: string | null;
  last_health_status: string | null;
  last_seen_at: string | null;
  reliability: AgentReliability | null;
};
export type AgentMessageEntry = {
  id: number;
  agent_code: string;
  asset_symbol: string | null;
  status: string;
  signal: string;
  confidence: number;
  evidence: Record<string, unknown>;
  risk_flags: string[];
  rationale: string | null;
  generated_at: string;
  expires_at: string | null;
};
export type Contradiction = {
  id: number;
  decision_id: number;
  agent_code_a: string;
  agent_code_b: string;
  signal_a: string;
  signal_b: string;
  severity: number;
  description: string;
};
export type Decision = {
  id: number;
  asset_symbol: string;
  ts: string;
  decision_state: string;
  consensus_score: number;
  contradiction_score: number;
  reasoning_summary: string;
  blocked_reason: string | null;
  critical_agent_failure: boolean;
};
export type DecisionDetail = Decision & {
  agent_inputs: Record<string, AgentMessageEntry & { evidence: Record<string, unknown> }>;
  contradictions: Contradiction[];
};

export const getAgents = (token: string) => apiFetch<Agent[]>("/api/agents", token);
export const getAgentMessages = (token: string, code: string, limit = 20) =>
  apiFetch<AgentMessageEntry[]>(`/api/agents/${code}/messages?limit=${limit}`, token);
export const getDecisions = (token: string, limit = 20) => apiFetch<Decision[]>(`/api/decisions?limit=${limit}`, token);
export const getDecisionDetail = (token: string, decisionId: number) =>
  apiFetch<DecisionDetail>(`/api/decisions/${decisionId}`, token);
export const getContradictions = (token: string, limit = 20) =>
  apiFetch<Contradiction[]>(`/api/contradictions?limit=${limit}`, token);

export async function restoreAgent(token: string, code: string) {
  const res = await fetch(`${API_URL}/api/agents/${code}/restore`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ confirm: true }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false as const, detail: body?.detail ?? `Restore failed (${res.status})` };
  return { ok: true as const, result: body as Agent };
}

export async function pauseTrading(token: string, reason: string) {
  const res = await fetch(`${API_URL}/api/trading/pause`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false as const, detail: body?.detail ?? `Pause failed (${res.status})` };
  return { ok: true as const, result: body as SystemStatus };
}

export async function resumeTrading(token: string) {
  const res = await fetch(`${API_URL}/api/trading/resume`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false as const, detail: body?.detail ?? `Resume failed (${res.status})` };
  return { ok: true as const, result: body as SystemStatus };
}

export async function closePaperPosition(token: string, positionId: number, reason: string | null) {
  const res = await fetch(`${API_URL}/api/trading/positions/${positionId}/close`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false as const, detail: body?.detail ?? `Close failed (${res.status})` };
  return { ok: true as const, result: body as Position };
}

export async function resetPaperAccount(token: string, confirm: boolean) {
  const res = await fetch(`${API_URL}/api/trading/reset-paper`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ confirm }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false as const, detail: body?.detail ?? `Reset failed (${res.status})` };
  return { ok: true as const, result: body as SystemStatus };
}

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

// --- "PROMPT 7" Strategy Lab -----------------------------------------------

export type BacktestJob = {
  id: number;
  kind: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type FullLabReport = {
  blocked: boolean;
  reason?: string | null;
  configuration?: Record<string, unknown>;
  data?: { bars_checked: number; issues: { severity: string; code: string; detail: string }[]; data_fingerprint: string | null };
  strategy?: Record<string, unknown>;
  performance?: Record<string, number | string | null>;
  risk?: Record<string, unknown>;
  drawdown?: Record<string, unknown>;
  walk_forward?: { consistent: boolean | null; reason: string; pooled_oos_expectancy: number | null; num_windows: number };
  monte_carlo?: { method: string; num_simulations: number; percentiles: Record<string, Record<string, number | null> | null>; probability_of_loss: number | null; probability_of_drawdown_threshold: number | null };
  stress_tests?: { scenario: string; return_delta: number | null; drawdown_delta: number | null; survived: boolean | null; notes: Record<string, unknown> }[];
  robustness?: { score: number; components: { name: string; score: number; max_score: number; evidence: string }[]; insufficient_evidence: string[] };
  parameter_stability?: { stable: boolean | null; reason: string };
  reality_gap?: { reference_backtest_id: number | null; expectancy_difference: number | null; win_rate_difference: number | null; drawdown_difference: number | null; notes: string[] };
  final_assessment?: { quality_score: number; status: string; assessment: string; reasons: string[]; failure_verdict: string; failure_reasons: string[] };
};

export type FullLabJobPayload = {
  strategy_id: number;
  asset_id: number;
  timeframe: string;
  start_ts: string;
  end_ts: string;
  initial_capital: number;
  monte_carlo_simulations?: number;
};

export async function createFullLabJob(token: string, payload: FullLabJobPayload) {
  const res = await fetch(`${API_URL}/api/backtests/jobs`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ kind: "full_lab", payload }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false as const, detail: body?.detail ?? `Strategy Lab run failed (${res.status})` };
  return { ok: true as const, job: body as BacktestJob };
}

export const getLabJob = (token: string, jobId: number) => apiFetch<BacktestJob>(`/api/backtests/jobs/${jobId}`, token);

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

// --- "PROMPT 10" Autonomous Research Lab ----------------------------------

export type ResearchReportHypothesis = {
  id: number;
  title: string;
  status: string;
  priority_score: number | null;
  source: string;
  risk: string;
};
export type ResearchReportExperiment = {
  id: number;
  type: string;
  status: string;
  strategy_code: string | null;
  changed_params: string[] | null;
  created_at: string | null;
};
export type ResearchReportDrift = { drift_type: string; entity: string; severity: string; ts: string | null };
export type ResearchReportFeatureSignal = {
  pattern_type: string;
  regime: string;
  expectancy: number | null;
  sample_size: number;
};
export type ResearchReportStrategyVersion = {
  id: number;
  strategy_code: string | null;
  version: string;
  lifecycle_status: string;
  validation_status: string;
};
export type ResearchReportKnowledgeEdge = {
  subject: string;
  relation: string;
  object: string;
  confidence: number;
  sample_size: number;
};
export type ResearchReportBudgetEntry = { used: number; limit: number; exhausted: boolean };
export type ResearchReportApproval = {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  created_at: string | null;
};
export type ResearchReport = {
  generated_at: string;
  executive_summary: {
    total_hypotheses: number;
    open_hypotheses: number;
    total_experiments_recent_window: number;
    completed_experiments_recent_window: number;
    promising_or_better_recent_window: number;
  };
  active_hypotheses: ResearchReportHypothesis[];
  recent_experiments: ResearchReportExperiment[];
  degradation_and_drift_alerts: ResearchReportDrift[];
  feature_research_findings: {
    pattern_signals_with_evidence: number;
    regime_dependent_signals: number;
    top_signals: ResearchReportFeatureSignal[];
  };
  strategy_versions: ResearchReportStrategyVersion[];
  knowledge_graph_highlights: ResearchReportKnowledgeEdge[];
  research_budget_usage: Record<string, ResearchReportBudgetEntry>;
  pending_approvals: ResearchReportApproval[];
  security_and_sandbox_posture: Record<string, string>;
  recommendations: string[];
};

export const getResearchReport = (token: string) => apiFetch<ResearchReport>("/api/research-lab/report", token);

export async function decideResearchApproval(token: string, approvalId: number, decision: string, detail?: string) {
  const res = await fetch(`${API_URL}/api/research-lab/approvals/${approvalId}/decide`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ decision, detail: detail ?? null }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false as const, detail: body?.detail ?? `Decision failed (${res.status})` };
  return { ok: true as const, result: body as ResearchReportApproval };
}

// --- "PROMPT 11" (Global Market Intelligence) ---------------------------

export type AssetUniverseEntry = {
  id: number;
  symbol: string;
  asset_class: string;
  exchange: string | null;
  status: string;
  liquidity_score: number | null;
  data_quality_score: number | null;
  is_active: boolean;
};
export type VolatilityEventEntry = {
  id: number;
  asset_id: number;
  ts: string;
  timeframe: string;
  event_type: string;
  realized_vol: number;
  percentile: number;
  regime: string;
};
export type AnomalyEntry = {
  id: number;
  asset_id: number;
  ts: string;
  anomaly_type: string;
  score: number;
  evidence: Record<string, unknown>;
  reviewed: boolean;
  explanation: string | null;
};
export type WatchlistEntryItem = {
  id: number;
  asset_id: number;
  reason: string;
  status: string;
  added_at: string;
  updated_at: string;
  removed_at: string | null;
  removal_reason: string | null;
};
export type OpportunityClusterEntry = {
  id: number;
  ts: string;
  signal_ids: number[];
  asset_ids: number[];
  direction: string;
  factor: string | null;
  avg_correlation: number;
  combined_risk: number;
  ranking_penalty: number;
};
export type MarketSessionEntry = {
  session: string;
  state: string;
  local_time: string;
  minutes_to_next_transition: number | null;
};
export type GlobalMarketSnapshot = {
  ts: string;
  sessions: MarketSessionEntry[];
  active_overlaps: string[][];
};

export const getMarketUniverse = (token: string) => apiFetch<AssetUniverseEntry[]>("/api/global-market/universe", token);
export const getVolatilityEvents = (token: string, limit = 20) =>
  apiFetch<VolatilityEventEntry[]>(`/api/global-market/volatility?limit=${limit}`, token);
export const getMarketAnomalies = (token: string, limit = 20) =>
  apiFetch<AnomalyEntry[]>(`/api/global-market/anomalies?limit=${limit}`, token);
export const getDynamicWatchlist = (token: string) => apiFetch<WatchlistEntryItem[]>("/api/global-market/watchlist", token);
export const getOpportunityClusters = (token: string, limit = 20) =>
  apiFetch<OpportunityClusterEntry[]>(`/api/global-market/clusters?limit=${limit}`, token);
export const getGlobalMarketSessions = (token: string) =>
  apiFetch<GlobalMarketSnapshot>("/api/global-market/sessions", token);

// --- "PROMPT 12" (Advanced Risk & Capital Defense Engine) ----------------

export type AdvancedRisk = {
  ts: string;
  risk_score: number;
  risk_state: string;
  capital_preservation_mode: boolean;
  zero_trade_mode: boolean;
  degraded: boolean;
  reasons: string[];
  equity: number | null;
  drawdown_pct: number | null;
  peak_equity: number | null;
  drawdown_state: string | null;
  drawdown_level: number | null;
  concentration_state: string | null;
  system_risk_state: string | null;
  execution_risk_state: string | null;
  model_risk_state: string | null;
  data_risk_state: string | null;
};
export type CircuitBreaker = { name: string; tripped: boolean; reason: string | null; scope_id: number | null };
export type ConcentrationCluster = {
  symbols: string[];
  direction: string;
  factor: string | null;
  avg_correlation: number;
  ranking_penalty: number;
};
export type Concentration = {
  open_position_count: number;
  total_exposure_notional: number;
  max_cluster_exposure_pct: number;
  concentration_state: string;
  asset_class_exposure_pct: Record<string, number>;
  hidden_factor_warnings: string[];
  clusters: ConcentrationCluster[];
};
export type KillSwitchState = { kill_switch_state: string; recovery_mode: boolean; trading_enabled: boolean };
export type RecoveryReadiness = { ready: boolean; reasons: string[] };

export const getAdvancedRisk = (token: string) => apiFetch<AdvancedRisk>("/api/risk/advanced", token);
export const getCircuitBreakers = (token: string) => apiFetch<CircuitBreaker[]>("/api/risk/breakers", token);
export const getConcentration = (token: string) => apiFetch<Concentration>("/api/risk/concentration", token);
export const getKillSwitchState = (token: string) => apiFetch<KillSwitchState>("/api/risk/kill-switch/state", token);

export async function startKillSwitchRecovery(token: string) {
  const res = await fetch(`${API_URL}/api/risk/kill-switch/recovery/start`, {
    method: "POST", headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
  });
  if (!res.ok) return null;
  return (await res.json()) as KillSwitchState;
}

export async function getRecoveryReadiness(token: string) {
  return apiFetch<RecoveryReadiness>("/api/risk/kill-switch/recovery/readiness", token);
}

export async function confirmKillSwitchRecovery(token: string, force: boolean) {
  const res = await fetch(`${API_URL}/api/risk/kill-switch/recovery/confirm?force=${force}`, {
    method: "POST", headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
  });
  if (!res.ok) return null;
  return (await res.json()) as KillSwitchState;
}

// --- "PROMPT 13" (Universal Broker & Exchange Connectivity) --------------

export type BrokerCapabilities = {
  supports_market_orders: boolean;
  supports_limit_orders: boolean;
  supports_stop_orders: boolean;
  supports_short: boolean;
  supports_fractional: boolean;
  supports_crypto: boolean;
  supports_stocks: boolean;
  supports_forex: boolean;
  supports_futures: boolean;
  supports_websocket: boolean;
};
export type Broker = {
  id: number;
  name: string;
  kind: string;
  status: string;
  is_default: boolean;
  configured: boolean;
  capabilities: BrokerCapabilities;
};
export type BrokerHealth = { broker_name: string; state: string; latency_ms: number | null; recent_error_count: number; reasons: string[] };
export type Account = {
  broker_name: string;
  balance: number;
  available_balance: number;
  equity: number;
  margin: number;
  margin_used: number;
  margin_available: number;
  currency: string;
  ts: string;
};
export type Execution = {
  id: number;
  order_id: number;
  broker_order_id: string | null;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  fee: number;
  fee_currency: string;
  slippage_bps: number | null;
  ts: string;
  liquidity: string;
  execution_mode: string;
};
export type ReconciliationRun = {
  id: number;
  broker_name: string;
  ts: string;
  ok: boolean;
  violations: string[];
  position_mismatches: string[];
  order_mismatches: string[];
  balance_diff: number | null;
};
export type ExecutionHealth = {
  evaluated: boolean;
  orders_evaluated: number;
  filled_orders: number;
  rejected_orders: number;
  fill_ratio: number | null;
  avg_latency_ms: number | null;
  avg_slippage_bps: number | null;
  avg_price_deviation_pct: number | null;
  market_impact_estimate_bps: number | null;
};

export const getBrokers = (token: string) => apiFetch<Broker[]>("/api/brokers", token);
export const getBrokerHealth = (token: string, brokerId: number) => apiFetch<BrokerHealth>(`/api/brokers/${brokerId}/health`, token);
export const getAccounts = (token: string) => apiFetch<Account[]>("/api/accounts", token);
export const getExecutions = (token: string) => apiFetch<Execution[]>("/api/executions?limit=20", token);
export const getReconciliationRuns = (token: string) => apiFetch<ReconciliationRun[]>("/api/reconciliation?limit=10", token);
export const getExecutionHealth = (token: string) => apiFetch<ExecutionHealth>("/api/execution/health", token);

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
