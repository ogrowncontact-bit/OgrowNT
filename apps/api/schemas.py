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
    role: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "viewer"


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
    # "PROMPT 11" §14/§20-24 -- closed-vocabulary classification, dedup key,
    # and decay timestamp. All three are nullable: enrichment happens on the
    # market_intelligence cadence (apps/worker/market_intelligence.py) after
    # the Signal already exists, so a just-created Signal can briefly have
    # none of them set yet -- an honest "not yet classified", not a bug.
    opportunity_type: str | None = None
    fingerprint: str | None = None
    expires_at: datetime | None = None


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
    # "PROMPT 11" §14/§20-24 -- see OpportunityOut's matching fields.
    opportunity_type: str | None = None
    fingerprint: str | None = None
    expires_at: datetime | None = None


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
    drawdown_levels: dict | None = None
    recovery: dict | None = None


# -- "PROMPT 12" Advanced Risk & Capital Defense Engine ---------------------


class AdvancedRiskOut(BaseModel):
    ts: datetime
    risk_score: float
    risk_state: str
    capital_preservation_mode: bool
    zero_trade_mode: bool
    degraded: bool
    reasons: list[str]
    equity: float | None = None
    drawdown_pct: float | None = None
    peak_equity: float | None = None
    drawdown_state: str | None = None
    drawdown_level: int | None = None
    concentration_state: str | None = None
    system_risk_state: str | None = None
    execution_risk_state: str | None = None
    model_risk_state: str | None = None
    data_risk_state: str | None = None


class CircuitBreakerOut(BaseModel):
    name: str
    tripped: bool
    reason: str | None
    scope_id: int | None = None


class ConcentrationClusterOut(BaseModel):
    symbols: list[str]
    direction: str
    factor: str | None
    avg_correlation: float
    ranking_penalty: float


class ConcentrationOut(BaseModel):
    open_position_count: int
    total_exposure_notional: float
    max_cluster_exposure_pct: float
    concentration_state: str
    asset_class_exposure_pct: dict[str, float]
    hidden_factor_warnings: list[str]
    clusters: list[ConcentrationClusterOut]


class PortfolioStressTestOut(BaseModel):
    """Distinct from StressTestOut (a single BACKTEST's stress-scenario
    result, "PROMPT 7") -- this is the LIVE portfolio's Monte Carlo/Risk of
    Ruin/VaR assessment ("PROMPT 12" §77-84)."""

    trades_used: int
    sufficient_history: bool
    monte_carlo: dict | None = None
    risk_of_ruin: dict | None = None
    var_pct: float | None = None
    cvar_pct: float | None = None
    var_confidence: float | None = None
    var_num_returns: int | None = None
    var_note: str | None = None


class RiskConfigVersionOut(BaseModel):
    version: int
    created_at: datetime
    approved_by: str | None
    reason: str
    status: str
    parameters: dict


class ConfigDiffOut(BaseModel):
    key: str
    old_value: object | None
    new_value: object | None


class RecoveryReadinessOut(BaseModel):
    ready: bool
    reasons: list[str]


class KillSwitchStateOut(BaseModel):
    kill_switch_state: str
    recovery_mode: bool
    trading_enabled: bool


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
    strategy_version: str | None = None
    code_version: str | None = None
    data_version: str | None = None
    random_seed: int | None = None


class BacktestDetailOut(BacktestSummaryOut):
    params: dict
    equity_curve: list[dict]
    trades: list[dict]
    notes: dict
    extra_metrics: dict = {}


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


# --- "PROMPT 7" (Backtesting Engine + Walk-Forward + Monte Carlo + Strategy Lab) --


class BacktestJobCreate(BaseModel):
    kind: str
    payload: dict


class BacktestJobOut(BaseModel):
    id: int
    kind: str
    status: str
    payload: dict
    result: dict
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DataIntegrityIssueOut(BaseModel):
    severity: str
    code: str
    detail: str


class DataIntegrityReportOut(BaseModel):
    blocked: bool
    status: str
    bars_checked: int
    issues: list[DataIntegrityIssueOut]


class TrainValidationTestSplitOut(BaseModel):
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    test_start: datetime
    test_end: datetime
    train_ratio: float
    validation_ratio: float
    test_ratio: float


class WalkForwardOptimizationRequest(BaseModel):
    strategy_id: int
    asset_id: int
    timeframe: str = "1m"
    start_ts: datetime
    end_ts: datetime
    train_days: float
    validation_days: float
    initial_capital: float = 10_000.0


class WalkForwardOptWindowOut(BaseModel):
    index: int
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    best_params: dict
    train_result: BacktestSummaryOut
    validation_result: BacktestSummaryOut


class WalkForwardOptimizationResponseOut(BaseModel):
    windows: list[WalkForwardOptWindowOut]
    pooled_oos_expectancy: float | None
    oos_positive_window_ratio: float | None
    parameter_stability: dict
    consistent: bool | None
    reason: str


class MonteCarloRequest(BaseModel):
    backtest_run_id: int
    method: str = "trade_reshuffling"
    num_simulations: int = 1000
    random_seed: int = 42
    drawdown_threshold_pct: float | None = None


class MonteCarloOut(BaseModel):
    id: int
    reference_backtest_run_id: int
    method: str
    num_simulations: int
    random_seed: int
    percentiles: dict
    probability_of_loss: float | None
    probability_of_drawdown_threshold: float | None
    drawdown_threshold_pct: float | None
    notes: dict
    created_at: datetime


class StressTestRequest(BaseModel):
    strategy_id: int
    asset_id: int
    timeframe: str = "1m"
    start_ts: datetime
    end_ts: datetime
    initial_capital: float = 10_000.0
    scenarios: list[str] | None = None


class StressTestOut(BaseModel):
    id: int
    reference_backtest_run_id: int
    scenario: str
    params: dict
    result: dict
    survived: bool | None
    created_at: datetime


class SensitivityRequest(BaseModel):
    strategy_id: int
    asset_id: int
    timeframe: str = "1m"
    start_ts: datetime
    end_ts: datetime
    initial_capital: float = 10_000.0
    kind: str = "cost"  # 'cost' | 'slippage' | 'capital'


class SensitivityPointOut(BaseModel):
    level: float
    net_return: float | None
    max_drawdown: float | None
    survived: bool | None


class SensitivityResponseOut(BaseModel):
    kind: str
    points: list[SensitivityPointOut]
    survives_all_levels: bool | None


class RiskOfRuinRequest(BaseModel):
    backtest_run_id: int
    drawdown_threshold_pct: float | None = None
    capital_loss_threshold_pct: float | None = None
    num_simulations: int = 1000
    random_seed: int = 42


class RiskOfRuinOut(BaseModel):
    probability_of_ruin: float | None
    drawdown_threshold_pct: float | None
    capital_loss_threshold_pct: float | None
    num_simulations: int
    random_seed: int
    assumptions: list[str]


class RealityGapOut(BaseModel):
    strategy_id: int
    reference_backtest_id: int | None
    return_difference: float | None
    win_rate_difference: float | None
    expectancy_difference: float | None
    drawdown_difference: float | None
    execution_difference: float | None
    notes: list[str]


class FailureVerdictOut(BaseModel):
    strategy_id: int
    verdict: str
    reasons: list[str]


class FullLabRequest(BaseModel):
    strategy_id: int
    asset_id: int
    timeframe: str = "1m"
    start_ts: datetime
    end_ts: datetime
    initial_capital: float = 10_000.0
    monte_carlo_simulations: int = 300
    random_seed: int = 42


class FullLabReportOut(BaseModel):
    blocked: bool
    reason: str | None = None
    configuration: dict | None = None
    data: dict | None = None
    strategy: dict | None = None
    performance: dict | None = None
    risk: dict | None = None
    drawdown: dict | None = None
    walk_forward: dict | None = None
    monte_carlo: dict | None = None
    stress_tests: list[dict] | None = None
    robustness: dict | None = None
    parameter_stability: dict | None = None
    reality_gap: dict | None = None
    final_assessment: dict | None = None


class StrategyLabComparisonRow(BaseModel):
    strategy_id: int
    strategy_code: str
    net_return: float | None
    max_drawdown: float | None
    expectancy: float | None
    profit_factor: float | None
    sharpe_like: float | None
    num_trades: int
    quality_score: float | None
    status: str | None


class StrategyLabCompareRequest(BaseModel):
    backtest_run_ids: list[int]


# --- "PROMPT 8" Autonomous Paper Trading ---------------------------------


class AutonomousStatusOut(BaseModel):
    status: str  # AutonomousSystemStatus — see packages/shared/worker_health.py
    trading_mode: str
    trading_enabled: bool
    trading_paused: bool
    paused_reason: str | None
    safety_belt_level: str
    worker_alive: bool
    worker_last_heartbeat: datetime | None
    open_positions_count: int
    worker_restart_count: int


class TradingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    event_type: str
    entity_type: str | None
    entity_id: int | None
    payload: dict


class ManualActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    actor: str
    action: str
    entity_type: str | None
    entity_id: int | None
    reason: str | None
    before: dict
    after: dict


class TradingPerformanceOut(BaseModel):
    trades_today: int
    wins_today: int
    losses_today: int
    win_rate_today: float | None
    daily_pnl: float
    open_positions_count: int
    exposure_pct: float
    drawdown_pct: float
    safety_belt_level: str
    autonomous_status: str


class PauseRequest(BaseModel):
    reason: str


class CloseOrCancelReasonRequest(BaseModel):
    reason: str | None = None


class ResetAccountRequest(BaseModel):
    confirm: bool = False


# --- "PROMPT 9" Multi-Agent Quant Intelligence Architecture --------------


class AgentReliabilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    as_of: datetime
    sample_size: int
    correct_count: int
    accuracy: float | None
    avg_confidence_when_correct: float | None
    avg_confidence_when_incorrect: float | None
    overconfidence_gap: float | None
    reliability_score: float | None


class AgentOut(BaseModel):
    code: str
    name: str
    directional: bool
    version: str
    status: str
    quarantined_at: datetime | None
    quarantine_reason: str | None
    last_health_status: str | None
    last_seen_at: datetime | None
    reliability: AgentReliabilityOut | None


class AgentMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    agent_code: str
    asset_symbol: str | None
    status: str
    signal: str
    confidence: float
    evidence: dict
    risk_flags: list
    rationale: str | None
    generated_at: datetime
    expires_at: datetime | None


class ContradictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    decision_id: int
    agent_code_a: str
    agent_code_b: str
    signal_a: str
    signal_b: str
    severity: float
    description: str


class DecisionOut(BaseModel):
    id: int
    asset_symbol: str
    ts: datetime
    decision_state: str
    consensus_score: float
    contradiction_score: float
    reasoning_summary: str
    blocked_reason: str | None
    critical_agent_failure: bool


class DecisionDetailOut(DecisionOut):
    agent_inputs: dict
    contradictions: list[ContradictionOut]


class RestoreAgentRequest(BaseModel):
    confirm: bool = True


# --- "PROMPT 10" Autonomous Research Lab ---------------------------------


class ResearchHypothesisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    problem: str
    observation: str
    hypothesis: str
    expected_effect: str
    risk: str
    assets: list
    timeframes: list
    regimes: list
    source: str
    quality: dict
    priority_score: float | None
    status: str
    created_at: datetime


class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    hypothesis_id: int | None
    type: str
    control: dict
    candidate: dict
    dataset: dict
    parameters: dict
    status: str
    result: dict | None
    reproducibility: dict
    created_at: datetime
    completed_at: datetime | None


class StrategyVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    strategy_id: int
    version: str
    parent_version_id: int | None
    changes: list
    dsl_definition: dict | None
    params: dict
    performance: dict
    validation_status: str
    lifecycle_status: str
    created_at: datetime
    created_by: str


class ResearchKnowledgeEdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject: str
    relation: str
    object: str
    confidence: float
    sample_size: int
    evidence: dict
    source_experiment_id: int | None
    created_at: datetime


class DriftDetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    drift_type: str
    entity: str
    detail: dict
    severity: str


class ResearchApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    entity_type: str
    entity_id: int
    action: str
    status: str
    reviewer: str | None
    reviewed_at: datetime | None
    evidence: dict
    detail: str | None
    created_at: datetime


class RequestApprovalRequest(BaseModel):
    entity_type: str
    entity_id: int
    action: str
    evidence: dict = {}
    detail: str | None = None


class ApprovalDecisionRequest(BaseModel):
    decision: str
    detail: str | None = None


class ResearchQueueItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    queue_type: str
    payload: dict
    status: str
    result: dict | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class EnqueueResearchJobRequest(BaseModel):
    queue_type: str
    payload: dict = {}


class ResearchBudgetStatusOut(BaseModel):
    resource_type: str
    period_hours: float
    used: float
    limit: float
    remaining: float
    exhausted: bool


# --- "PROMPT 11" (Global Market Intelligence) ---------------------------


class AssetUniverseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    asset_class: str
    exchange: str | None
    status: str
    liquidity_score: float | None
    data_quality_score: float | None
    is_active: bool


class VolatilityEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    asset_id: int
    ts: datetime
    timeframe: str
    event_type: str
    realized_vol: float
    percentile: float
    regime: str


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    asset_id: int
    ts: datetime
    anomaly_type: str
    score: float
    evidence: dict
    reviewed: bool
    explanation: str | None


class WatchlistEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    asset_id: int
    reason: str
    status: str
    added_at: datetime
    updated_at: datetime
    removed_at: datetime | None
    removal_reason: str | None


class OpportunityClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    signal_ids: list
    asset_ids: list
    direction: str
    factor: str | None
    avg_correlation: float
    combined_risk: float
    ranking_penalty: float


class MarketSessionOut(BaseModel):
    session: str
    state: str
    local_time: str
    minutes_to_next_transition: int | None


class GlobalMarketSnapshotOut(BaseModel):
    ts: datetime
    sessions: list[MarketSessionOut]
    active_overlaps: list[list[str]]


class StructureReadingOut(BaseModel):
    symbol: str
    structure: str
    break_state: str
    range_high: float | None
    range_low: float | None
    reason: str | None


# Score ≠ probability -- see packages/market/pairs.py's module docstring:
# this is experimental research, never an execution signal.
class PairSignalOut(BaseModel):
    symbol_a: str
    symbol_b: str
    hedge_ratio: float
    zscore: float
    looks_mean_reverting: bool
    autocorrelation: float
    sample_size: int
    disclaimer: str


class HistoricalAnalogOut(BaseModel):
    sample_size: int
    win_rate: float | None
    outcome_counts: dict
    realized_pnl_samples: list[float]
    worst_pnl: float | None
    quality: str
    disclaimer: str
