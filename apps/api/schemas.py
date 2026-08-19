from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    asset_class: str
    exchange: str | None
    is_active: bool


class AssetCreate(BaseModel):
    symbol: str
    asset_class: str
    exchange: str | None = None
    base_currency: str | None = None
    quote_currency: str | None = None


class AssetUpdate(BaseModel):
    is_active: bool


class CandleOut(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    data_quality: str


class ComponentHealth(BaseModel):
    name: str
    status: str  # "green" | "yellow" | "red"
    detail: str | None = None


class HealthResponse(BaseModel):
    overall: str  # "green" | "degraded"
    components: list[ComponentHealth]


class SystemStatusResponse(BaseModel):
    safety_belt_level: str
    trading_enabled: bool
    updated_at: datetime
    updated_reason: str | None


class PortfolioResponse(BaseModel):
    equity: float
    cash: float
    exposure_pct: float
    daily_pnl: float
    drawdown_pct: float
    safety_belt_level: str
    as_of: datetime
    # Prompt 4 §16/§29 — computed fresh via packages/portfolio/state.py's
    # compute_state() (not persisted per-row, same as weekly already wasn't:
    # both are cheap to re-derive from portfolio_snapshots equity history).
    weekly_pnl: float
    weekly_loss_pct: float
    monthly_pnl: float
    monthly_loss_pct: float


class ExposureItem(BaseModel):
    key: str
    notional: float
    pct_of_equity: float


class CorrelationPairOut(BaseModel):
    asset_symbol_a: str
    asset_symbol_b: str
    correlation: float
    ts: datetime


class PortfolioExposureOut(BaseModel):
    """Risk Center concentration breakdown — docs/blueprint/08-risk-engine.md
    §Concentration Guard. Powers the dashboard's Risk Heatmap (Prompt 4 §31)."""

    equity: float
    by_asset: list[ExposureItem]
    by_strategy: list[ExposureItem]
    by_direction: list[ExposureItem]
    correlations: list[CorrelationPairOut]


class PortfolioSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ts: datetime
    equity: float
    cash: float
    exposure_pct: float
    daily_pnl: float
    drawdown_pct: float
    safety_belt_level: str


# --- Phase 2 ---------------------------------------------------------------


class StrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    family: str
    version: str
    lifecycle_stage: str


class StrategyPerformanceOut(BaseModel):
    strategy_id: int
    total_trades: int
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    note: str


class RegimeOut(BaseModel):
    asset_symbol: str
    timeframe: str
    ts: datetime
    regime: str
    confidence: float
    features: dict


class OpportunityOut(BaseModel):
    signal_id: int
    asset_symbol: str
    strategy_code: str
    strategy_name: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float | None
    risk_reward: float
    regime: str
    final_score: float
    # 0-100: how much the score's inputs can be trusted, shown separately
    # from final_score per Prompt 3 §17 — never a synonym for it.
    confidence: float
    tier: str
    ts: datetime


class ScoreBreakdown(BaseModel):
    technical: float
    pattern: float
    regime_fit: float
    historical_edge: float
    liquidity: float
    news: float
    risk_reward: float
    strategy_performance: float
    volatility_penalty: float
    correlation_penalty: float
    execution_cost_penalty: float
    drawdown_penalty: float
    final_score: float
    confidence: float
    tier: str
    notes: dict


class EvidenceItemOut(BaseModel):
    kind: str  # "confirm" | "warning"
    text: str


class OpportunityDetailOut(BaseModel):
    signal_id: int
    asset_symbol: str
    strategy_code: str
    strategy_name: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float | None
    risk_reward: float
    regime: str
    regime_confidence: float
    status: str
    ts: datetime
    score: ScoreBreakdown
    # Prompt 3 §23 — "WHY THIS OPPORTUNITY EXISTS": structured, deterministic
    # justifications only, never the model's private reasoning.
    evidence: list[EvidenceItemOut]


# --- Phase 3 -----------------------------------------------------------


class RiskCheckOut(BaseModel):
    check_name: str
    passed: bool
    detail: dict


class RiskDecisionOut(BaseModel):
    signal_id: int
    asset_symbol: str
    strategy_code: str
    approved: bool
    approved_size: float | None
    reason: str
    safety_belt_level: str
    created_at: datetime
    checks: list[RiskCheckOut] = []
    # Prompt 4 §25/26 enrichment, derived from the same persisted checks
    # above (never a schema/column rename) — decision is "blocked" when not
    # approved, "reduced" when approved at less than full size (belt and/or
    # strategy-health multiplier < 1.0), "approved" otherwise.
    decision: str
    reasons: list[str] = []
    risk_amount: float | None = None
    position_size: float | None = None
    risk_reward: float | None = None


class RiskStateOut(BaseModel):
    safety_belt_level: str
    trading_enabled: bool
    limits: dict
    recent_decisions: list[RiskDecisionOut]


class RiskLimitsUpdate(BaseModel):
    """Partial update — only send the keys you want to change, nested the
    same way as config/risk_limits.yaml (e.g. {"per_trade": {"max_risk_pct": 0.5}})."""

    capital: dict | None = None
    per_trade: dict | None = None
    portfolio: dict | None = None
    loss_limits: dict | None = None
    liquidity: dict | None = None
    data_quality: dict | None = None
    safety_belt_multipliers: dict | None = None
    news_risk_multipliers: dict | None = None


class PositionOut(BaseModel):
    id: int
    asset_symbol: str
    strategy_code: str
    direction: str
    entry_price: float
    current_stop: float
    target_price: float | None
    size: float
    opened_at: datetime
    closed_at: datetime | None
    status: str
    unrealized_pnl: float | None
    realized_pnl: float | None
    exit_price: float | None
    exit_reason: str | None


class OrderOut(BaseModel):
    id: int
    position_id: int | None
    side: str
    order_type: str
    qty: float
    status: str
    filled_price: float | None
    fees: float | None
    slippage_bps: float | None
    submitted_at: datetime | None
    filled_at: datetime | None
    is_paper: bool


class TradeOut(BaseModel):
    id: int
    position_id: int
    asset_symbol: str
    strategy_code: str
    direction: str
    pnl: float
    r_multiple: float | None
    outcome: str
    is_paper: bool
    closed_at: datetime


class TradeWhyOut(BaseModel):
    trade: TradeOut
    position: PositionOut
    opportunity: OpportunityDetailOut | None
    risk_decision: RiskDecisionOut | None


# --- Phase 4 -----------------------------------------------------------


class NewsImpactOut(BaseModel):
    asset_symbol: str
    direction: str
    impact: str
    confidence: float
    horizon_hours: float
    rationale: str
    is_direct: bool


class NewsEventOut(BaseModel):
    id: int
    source: str
    published_at: datetime
    headline: str
    category: str | None
    impacts: list[NewsImpactOut]
    # Prompt 6 News Intelligence additions.
    source_quality_score: float
    sentiment: str
    sentiment_confidence: float
    importance: str
    novelty_score: float
    impact_score: float
    cluster_id: int | None
    source_consensus_score: float
    has_conflicting_sources: bool
    entities: list[dict]


class MacroEventOut(BaseModel):
    id: int
    event: str
    country: str
    currency: str | None
    scheduled_at: datetime
    importance: str
    forecast: float | None
    previous: float | None
    actual: float | None
    surprise: float | None
    status: str


class NewsRiskOut(BaseModel):
    level: str
    size_multiplier: float
    blocked: bool
    reasons: list[str]


class RecentNewsItemOut(BaseModel):
    news_event_id: int
    headline: str
    source: str
    published_at: datetime
    sentiment: str
    importance: str
    direction: str
    impact: str
    confidence: float
    is_direct: bool


class NewsMomentumOut(BaseModel):
    count_lookback: int
    count_recent: int
    high_importance_count: int
    distinct_sources: int
    sentiment_mix: dict
    level: str


class SentimentShiftOut(BaseModel):
    recent_bullish_share: float | None
    baseline_bullish_share: float | None
    recent_count: int
    baseline_count: int
    shift: float | None
    detected: bool


class AssetNewsContextOut(BaseModel):
    asset_id: int
    asset_symbol: str
    recent_news: list[RecentNewsItemOut]
    momentum: NewsMomentumOut | None
    sentiment_shift: SentimentShiftOut | None
    avg_source_quality: float | None


class PatternOut(BaseModel):
    id: int
    asset_symbol: str
    timeframe: str
    ts: datetime
    pattern_type: str
    pattern_class: str
    direction: str | None
    strength: float
    confidence: float


class PatternPerformanceOut(BaseModel):
    pattern_type: str
    regime: str
    sample_size: int
    win_rate: float | None
    avg_r_multiple: float | None
    expectancy: float | None
    updated_at: datetime


# --- Phase 5 -----------------------------------------------------------


class StrategyLearningOut(BaseModel):
    strategy_id: int
    strategy_code: str
    lifecycle_stage: str
    as_of: datetime | None
    window_trades: int
    total_trades: int
    win_rate: float | None
    profit_factor: float | None
    avg_win: float | None
    avg_loss: float | None
    sharpe: float | None
    max_drawdown: float | None
    expectancy: float | None
    best_regime: str | None
    worst_regime: str | None
    health_score: float | None


class TradeJournalOut(BaseModel):
    trade_id: int
    asset_symbol: str
    strategy_code: str
    expected_outcome: str
    actual_outcome: str
    hypothesis: str | None
    root_cause: str | None
    created_at: datetime


class LearnedRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scope: str
    condition: dict
    conclusion: str
    confidence: float
    sample_size: int
    status: str
    created_at: datetime
    validated_at: datetime | None


class MarketMemoryOut(BaseModel):
    id: int
    ts: datetime
    asset_symbol: str | None
    context: dict
    outcome: str | None


class StrategyRestoreRequest(BaseModel):
    to_stage: str = "paper"


# --- Phase 6 -----------------------------------------------------------


class BacktestRequest(BaseModel):
    strategy_id: int
    asset_id: int
    timeframe: str = "1m"
    start_ts: datetime
    end_ts: datetime
    initial_capital: float = 10_000.0


class BacktestSummaryOut(BaseModel):
    id: int
    strategy_code: str
    asset_symbol: str
    timeframe: str
    kind: str
    group_label: str | None
    window_index: int | None
    total_windows: int | None
    start_ts: datetime
    end_ts: datetime
    initial_capital: float
    net_return: float | None
    cagr_like_return: float | None
    win_rate: float | None
    profit_factor: float | None
    max_drawdown: float | None
    avg_trade: float | None
    expectancy: float | None
    num_trades: int
    sharpe_like: float | None
    created_at: datetime


class BacktestDetailOut(BacktestSummaryOut):
    params: dict
    equity_curve: list[dict]
    trades: list[dict]
    notes: dict


class WalkForwardRequest(BaseModel):
    strategy_id: int
    asset_id: int
    timeframe: str = "1m"
    start_ts: datetime
    end_ts: datetime
    window_days: float
    initial_capital: float = 10_000.0


class WalkForwardResponseOut(BaseModel):
    group_label: str
    windows: list[BacktestSummaryOut]
    consistent: bool | None
    reason: str


class PromotionCheckOut(BaseModel):
    strategy_id: int
    eligible: bool
    current_stage: str
    next_stage: str | None
    reasons: list[str]
    criteria: dict
    actual: dict


# --- Phase 7 -----------------------------------------------------------


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    severity: str
    category: str
    message: str
    meta: dict
    acknowledged: bool
    delivered_at: datetime | None


class OptimizeRequest(BaseModel):
    strategy_id: int
    asset_id: int
    timeframe: str = "1m"
    start_ts: datetime
    end_ts: datetime
    window_days: float
    initial_capital: float = 10_000.0
    multipliers: list[float] | None = None
    max_combinations: int | None = None


class OptimizeCandidateOut(BaseModel):
    params: dict
    group_label: str
    windows: list[BacktestSummaryOut]
    consistent: bool | None
    walk_forward_reason: str


class OptimizeResponseOut(BaseModel):
    candidates: list[OptimizeCandidateOut]
    best_params: dict | None
    reason: str


class EquityPointOut(BaseModel):
    ts: datetime
    equity: float
    drawdown_pct: float


class TradeStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_trades: int
    win_rate: float | None
    expectancy: float | None
    profit_factor: float | None
    avg_pnl: float | None


class DrawdownStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    current_drawdown_pct: float | None
    max_drawdown_pct: float | None
    peak_equity: float | None


class PatternLeaderboardEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pattern_type: str
    regime: str
    sample_size: int
    win_rate: float | None
    expectancy: float | None


class AnalyticsOverviewOut(BaseModel):
    equity_curve: list[EquityPointOut]
    trade_stats: TradeStatsOut
    drawdown: DrawdownStatsOut
    tier_distribution: dict[str, int]
    pattern_leaderboard: list[PatternLeaderboardEntryOut]
    regime_distribution: dict[str, int]


# --- Prompt 2: market data engine + scanner ----------------------------


class DataSourceOut(BaseModel):
    """Shown verbatim on the dashboard so mock and real data are never
    mistaken for each other (Prompt 2 §4)."""

    provider: str
    is_live: bool


class MarketAssetOverviewOut(BaseModel):
    symbol: str
    asset_class: str
    price: float | None
    pct_change: float | None
    volatility: float | None
    volume: float | None
    trend: str | None
    data_quality_score: int | None
    data_quality_status: str | None
    last_update: datetime | None


class MarketOverviewOut(BaseModel):
    data_source: DataSourceOut
    assets: list[MarketAssetOverviewOut]


class MarketEventOut(BaseModel):
    id: int
    asset_symbol: str
    event_type: str
    timeframe: str
    severity: str
    price: float | None
    volume: float | None
    confidence: float
    meta: dict
    ts: datetime


class DataQualityOut(BaseModel):
    symbol: str
    quality_score: int
    status: str
    components: dict[str, float]
    detail: str | None = None
