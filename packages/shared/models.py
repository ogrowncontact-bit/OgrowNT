"""SQLAlchemy models — incremental subset of docs/blueprint/02-database-schema.md.

Tables are added phase by phase, matching what's actually implemented and
running (docs/blueprint/12-roadmap.md), not stubbed out ahead of the code
that uses them:
  Phase 1: auth, assets, OHLCV, paper portfolio, system state, alerts, audit log
  Phase 2: strategies, market regimes, signals, opportunity scores
  Phase 3: risk checks/decisions, positions, orders, trades, correlation matrix
  Phase 4: news events/impact, patterns, pattern performance
  Phase 5: strategy performance/health, trade journal, learned rules, market memory
  Phase 6: backtest runs
macro_events (from the blueprint schema) is not yet implemented — out of
scope for every phase planned so far; a macro economic calendar is a
natural but separate future addition.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminUser(Base):
    """Single-tenant admin account. See docs/blueprint/03-api-spec.md#auth."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "asset_class IN ('crypto','forex','equity','index','commodity')",
            name="ck_assets_asset_class",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    asset_class: Mapped[str] = mapped_column(String, nullable=False)
    exchange: Mapped[str | None] = mapped_column(String)
    base_currency: Mapped[str | None] = mapped_column(String)
    quote_currency: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class OHLCV(Base):
    """Plain (non-hypertable) OHLCV storage for Phase 1.

    Promote to a TimescaleDB hypertable (see docs/blueprint/02-database-schema.md)
    once the deployment target has the extension available — the table shape
    does not change, only how it is partitioned.
    """

    __tablename__ = "ohlcv"
    __table_args__ = (
        CheckConstraint(
            "timeframe IN ('1m','5m','15m','1h','4h','1D','1W')",
            name="ck_ohlcv_timeframe",
        ),
    )

    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    data_quality: Mapped[str] = mapped_column(String, default="high", nullable=False)

    asset: Mapped["Asset"] = relationship()


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    exposure_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    daily_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    safety_belt_level: Mapped[str] = mapped_column(String, default="normal", nullable=False)


class SystemState(Base):
    """Singleton row — see docs/blueprint/02-database-schema.md#system_state."""

    __tablename__ = "system_state"

    id: Mapped[bool] = mapped_column(Boolean, primary_key=True, default=True)
    safety_belt_level: Mapped[str] = mapped_column(String, default="normal", nullable=False)
    trading_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    updated_reason: Mapped[str | None] = mapped_column(Text)
    # Written once per full loop iteration by
    # packages/shared/worker_health.record_heartbeat (called from
    # apps/worker/main.py) — lets /api/system/health honestly report whether
    # the 24/7 loop is actually alive, instead of only checking components
    # (database, market data, ...) that could all be green while the worker
    # process itself is dead or stuck.
    worker_last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("severity IN ('info','warning','critical')", name="ck_alerts_severity"),
        CheckConstraint(
            "category IN ('trade','risk','loss','emergency','learning','system')",
            name="ck_alerts_category",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Phase 7 (packages/notifications): when a delivery attempt was last made
    # to the configured channels — not "delivered successfully", since a
    # channel failure or "not configured" is still a completed attempt, just
    # like every other honest-degradation state in this codebase. Per-channel
    # outcomes live in meta["_delivery"] (packages/worker/alerts.py), not a
    # separate column, since the channel set is itself configurable.
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String)
    entity_id: Mapped[int | None] = mapped_column()
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


# --- Phase 2 (Intelligence) ---------------------------------------------


class StrategyRow(Base):
    """A registered strategy — see docs/blueprint/04-agents-architecture.md#agent-07.

    Named StrategyRow (not Strategy) to avoid clashing with the pluggable
    strategy classes in packages/quant/strategies — this is the DB record
    about a strategy, not the strategy's logic.
    """

    __tablename__ = "strategies"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_stage IN ('idea','backtest','out_of_sample','paper',"
            "'small_capital','production','quarantine','retired')",
            name="ck_strategies_lifecycle_stage",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    family: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False, default="1.0")
    lifecycle_stage: Mapped[str] = mapped_column(String, default="idea", nullable=False)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class MarketRegime(Base):
    """See docs/blueprint/04-agents-architecture.md#agent-06 and
    docs/blueprint/02-database-schema.md#market_regimes. Phase 2 only ever
    writes trending_bull/trending_bear/ranging/high_volatility/low_volatility
    (packages/quant/regime/classifier.py) — panic/euphoria/transition need
    the Phase 4 News Intelligence Agent to be distinguishable.
    """

    __tablename__ = "market_regimes"
    __table_args__ = (
        CheckConstraint(
            "regime IN ('trending_bull','trending_bear','ranging','high_volatility',"
            "'low_volatility','panic','euphoria','transition','unknown')",
            name="ck_market_regimes_regime",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"))
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    regime: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    features: Mapped[dict] = mapped_column(JSON, default=dict)


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint("direction IN ('long','short')", name="ck_signals_direction"),
        CheckConstraint(
            "status IN ('pending','scored','risk_rejected','approved','executed','expired')",
            name="ck_signals_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_price: Mapped[float] = mapped_column(Float, nullable=False)
    target_price: Mapped[float | None] = mapped_column(Float)
    regime_id: Mapped[int | None] = mapped_column(ForeignKey("market_regimes.id"))
    pattern_id: Mapped[int | None] = mapped_column(ForeignKey("patterns.id"))
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    strategy: Mapped["StrategyRow"] = relationship()
    asset: Mapped["Asset"] = relationship()
    regime: Mapped["MarketRegime | None"] = relationship()
    pattern: Mapped["Pattern | None"] = relationship()


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"
    __table_args__ = (
        UniqueConstraint("signal_id", name="uq_opportunity_scores_signal_id"),
        CheckConstraint(
            "tier IN ('ignore','watch','possible','high_quality','exceptional')",
            name="ck_opportunity_scores_tier",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id"), nullable=False)
    technical: Mapped[float] = mapped_column(Float, nullable=False)
    pattern: Mapped[float] = mapped_column(Float, nullable=False)
    regime_fit: Mapped[float] = mapped_column(Float, nullable=False)
    historical_edge: Mapped[float] = mapped_column(Float, nullable=False)
    liquidity: Mapped[float] = mapped_column(Float, nullable=False)
    news: Mapped[float] = mapped_column(Float, nullable=False)
    risk_reward: Mapped[float] = mapped_column(Float, nullable=False)
    strategy_performance: Mapped[float] = mapped_column(Float, nullable=False)
    volatility_penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    correlation_penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    execution_cost_penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    drawdown_penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    signal: Mapped["Signal"] = relationship()


# --- Phase 3 (Risk & Execution) -----------------------------------------


class RiskCheck(Base):
    """One row per check in the Risk Engine's Decision Pipeline
    (docs/blueprint/08-risk-engine.md) for a given signal — the audit trail
    behind the "Why?" panel's risk side.
    """

    __tablename__ = "risk_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id"), nullable=False)
    check_name: Mapped[str] = mapped_column(String, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RiskDecision(Base):
    __tablename__ = "risk_decisions"
    __table_args__ = (UniqueConstraint("signal_id", name="uq_risk_decisions_signal_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id"), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approved_size: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    safety_belt_level: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    signal: Mapped["Signal"] = relationship()


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("direction IN ('long','short')", name="ck_positions_direction"),
        CheckConstraint("status IN ('open','closed')", name="ck_positions_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"))
    direction: Mapped[str] = mapped_column(String, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_stop: Mapped[float] = mapped_column(Float, nullable=False)
    target_price: Mapped[float | None] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    realized_pnl: Mapped[float | None] = mapped_column(Float)
    unrealized_pnl: Mapped[float | None] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String)

    asset: Mapped["Asset"] = relationship()
    strategy: Mapped["StrategyRow"] = relationship()
    signal: Mapped["Signal | None"] = relationship()


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("order_type IN ('market','limit','stop')", name="ck_orders_order_type"),
        CheckConstraint("side IN ('buy','sell')", name="ck_orders_side"),
        CheckConstraint(
            "status IN ('new','submitted','filled','partially_filled','cancelled','rejected')",
            name="ck_orders_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"))
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"))
    broker_order_id: Mapped[str | None] = mapped_column(String)
    order_type: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="new", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filled_price: Mapped[float | None] = mapped_column(Float)
    fees: Mapped[float | None] = mapped_column(Float)
    slippage_bps: Mapped[float | None] = mapped_column(Float)
    is_paper: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (CheckConstraint("outcome IN ('win','loss','breakeven')", name="ck_trades_outcome"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), nullable=False)
    opened_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    closed_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    pnl: Mapped[float] = mapped_column(Float, nullable=False)
    r_multiple: Mapped[float | None] = mapped_column(Float)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    is_paper: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    position: Mapped["Position"] = relationship()


class CorrelationMatrixEntry(Base):
    __tablename__ = "correlation_matrix"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    asset_id_a: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    asset_id_b: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    window_days: Mapped[int] = mapped_column(primary_key=True)
    correlation: Mapped[float] = mapped_column(Float, nullable=False)


# --- Phase 4 (News, Regime, Patterns) -----------------------------------


class NewsEvent(Base):
    """A real news item from a configured source — never fabricated. See
    docs/blueprint/04-agents-architecture.md#agent-03: ingestion is
    deterministic (packages/data/connectors/news), interpretation (below,
    NewsImpact) is the only LLM-touched part of this table pair.
    """

    __tablename__ = "news_events"
    __table_args__ = (
        CheckConstraint(
            "category IN ('central_bank','inflation','employment','gdp','geopolitics',"
            "'regulation','crypto','earnings','m_and_a','other')",
            name="ck_news_events_category",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    raw_url: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class NewsImpact(Base):
    """LLM interpretation of one (news_event, asset) pair — the only table
    in this schema an LLM writes to directly, and even then only through
    packages/llm, never packages/execution (docs/blueprint/01-repo-structure.md
    §Regras de dependência).
    """

    __tablename__ = "news_impact"
    __table_args__ = (
        CheckConstraint("impact IN ('low','medium','high')", name="ck_news_impact_impact"),
        CheckConstraint("direction IN ('bullish','bearish','neutral')", name="ck_news_impact_direction"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_news_impact_confidence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    news_event_id: Mapped[int] = mapped_column(ForeignKey("news_events.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    impact: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    horizon_hours: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    news_event: Mapped["NewsEvent"] = relationship()
    asset: Mapped["Asset"] = relationship()


class Pattern(Base):
    __tablename__ = "patterns"
    __table_args__ = (
        CheckConstraint(
            "pattern_class IN ('technical','statistical','cross_market')", name="ck_patterns_pattern_class"
        ),
        CheckConstraint("direction IN ('bullish','bearish','neutral')", name="ck_patterns_direction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    pattern_type: Mapped[str] = mapped_column(String, nullable=False)
    pattern_class: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str | None] = mapped_column(String)
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    asset: Mapped["Asset"] = relationship()


class PatternPerformance(Base):
    """Rolling performance of a pattern type within a regime — updated by
    the Trade Monitor when a position whose signal was linked to a pattern
    closes (docs/blueprint/06-memory-system.md's Pattern Memory, minus the
    full Learning Engine writeback that arrives Phase 5).
    """

    __tablename__ = "pattern_performance"

    pattern_type: Mapped[str] = mapped_column(String, primary_key=True)
    regime: Mapped[str] = mapped_column(String, primary_key=True)
    sample_size: Mapped[int] = mapped_column(default=0, nullable=False)
    win_rate: Mapped[float | None] = mapped_column(Float)
    avg_r_multiple: Mapped[float | None] = mapped_column(Float)
    expectancy: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


# --- Phase 5 (Learning & Research) ---------------------------------------


class StrategyPerformance(Base):
    """Rolling-window strategy stats, recomputed by the Learning Agent's DET
    half on every trade close (docs/blueprint/04-agents-architecture.md
    #agent-13, docs/blueprint/02-database-schema.md §5). `health_score` is
    an implementation addition beyond the blueprint's SQL sketch: the doc
    only says "strategy health score" is recalculated alongside this row,
    without naming where it lives — storing it here (same DET computation,
    same cadence) avoids a redundant table.
    """

    __tablename__ = "strategy_performance"

    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, default=_utcnow)
    window_trades: Mapped[int] = mapped_column(nullable=False)
    total_trades: Mapped[int] = mapped_column(nullable=False)
    win_rate: Mapped[float | None] = mapped_column(Float)
    profit_factor: Mapped[float | None] = mapped_column(Float)
    avg_win: Mapped[float | None] = mapped_column(Float)
    avg_loss: Mapped[float | None] = mapped_column(Float)
    sharpe: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    expectancy: Mapped[float | None] = mapped_column(Float)
    best_regime: Mapped[str | None] = mapped_column(String)
    worst_regime: Mapped[str | None] = mapped_column(String)
    health_score: Mapped[float | None] = mapped_column(Float)

    strategy: Mapped["StrategyRow"] = relationship()


class TradeJournal(Base):
    """Expected-vs-actual outcome record for every closed trade — Failure
    Memory reads this filtered to actual_outcome != 'win'
    (docs/blueprint/06-memory-system.md). `hypothesis`/`root_cause` are
    filled by the Learning Agent's LLM half only when the two diverge, and
    stay null (never fabricated) when no LLM is configured.
    """

    __tablename__ = "trade_journal"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), unique=True, nullable=False)
    expected_outcome: Mapped[str] = mapped_column(String, nullable=False)
    actual_outcome: Mapped[str] = mapped_column(String, nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    action_taken: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    trade: Mapped["Trade"] = relationship()


class LearnedRule(Base):
    """Research Memory: a candidate rule proposed by the Research Agent's
    LLM half, only reaching `status='validated'` through a DET statistical
    check (sample size + significance) — never applied automatically to
    strategy behavior, only surfaced for the "what did the system learn"
    view (docs/blueprint/04-agents-architecture.md#agent-14).
    """

    __tablename__ = "learned_rules"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate','validated','rejected','retired')", name="ck_learned_rules_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    condition: Mapped[dict] = mapped_column(JSON, nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String, default="candidate", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketMemory(Base):
    """"Have I seen a market context like this before, and what happened?"
    (docs/blueprint/06-memory-system.md). The blueprint schema calls for a
    pgvector `embedding VECTOR(1536)` column with cosine-distance search;
    this Postgres deployment doesn't have the pgvector extension installed
    (verified: not even in pg_available_extensions), and there's no
    embedding model wired in yet. Rather than fabricate vectors or fake a
    similarity search, `embedding` is deferred entirely — the same explicit
    "not real yet" pattern as OHLCV's hypertable promotion — and
    `packages/quant/learning/memory.py` does structured similarity
    (regime + pattern + direction match) over `context` instead.
    TODO(real-embeddings): add the pgvector extension + a real embedding
    model and swap in cosine-distance search once available.
    """

    __tablename__ = "market_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"))
    context: Mapped[dict] = mapped_column(JSON, nullable=False)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"))
    outcome: Mapped[str | None] = mapped_column(String)

    asset: Mapped["Asset | None"] = relationship()


# --- Phase 6 (Backtesting) ------------------------------------------------


class BacktestRun(Base):
    """One event-driven backtest run (packages/backtest/engine.py) —
    docs/blueprint/10-backtesting-paper-trading.md's "Backtest Engine".
    Not in the blueprint's SQL sketch verbatim (02-database-schema.md has no
    backtest table; 03-api-spec.md only names the read endpoint
    `/api/research/experiments/{id}`) — this is the concrete schema behind
    that endpoint, one row per run whether it's a plain backtest, an
    out-of-sample check, or a single window of a walk-forward batch
    (`group_label`/`window_index`/`total_windows` tie those together).
    `params` records the exact strategy parameters used (defaults unless a
    parameter-stability check perturbed them) so every result stays
    reproducible and auditable, per docs/blueprint/00-overview.md.
    """

    __tablename__ = "backtest_runs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('backtest','out_of_sample','walk_forward_window','stability_check')",
            name="ck_backtest_runs_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, default="backtest", nullable=False)
    group_label: Mapped[str | None] = mapped_column(String)
    window_index: Mapped[int | None] = mapped_column()
    total_windows: Mapped[int | None] = mapped_column()
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)

    net_return: Mapped[float | None] = mapped_column(Float)
    cagr_like_return: Mapped[float | None] = mapped_column(Float)
    win_rate: Mapped[float | None] = mapped_column(Float)
    profit_factor: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    avg_trade: Mapped[float | None] = mapped_column(Float)
    expectancy: Mapped[float | None] = mapped_column(Float)
    num_trades: Mapped[int] = mapped_column(default=0, nullable=False)
    sharpe_like: Mapped[float | None] = mapped_column(Float)

    equity_curve: Mapped[list] = mapped_column(JSON, default=list)
    trades: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    strategy: Mapped["StrategyRow"] = relationship()
    asset: Mapped["Asset"] = relationship()
