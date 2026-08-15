"""SQLAlchemy models — incremental subset of docs/blueprint/02-database-schema.md.

Tables are added phase by phase, matching what's actually implemented and
running (docs/blueprint/12-roadmap.md), not stubbed out ahead of the code
that uses them:
  Phase 1: auth, assets, OHLCV, paper portfolio, system state, alerts, audit log
  Phase 2: strategies, market regimes, signals, opportunity scores
Tables for news/patterns (Phase 4), risk decisions/positions/orders/trades
(Phase 3), and memory/learning (Phase 5) are specified in the blueprint and
arrive with those phases.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    JSON,
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
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    strategy: Mapped["StrategyRow"] = relationship()
    asset: Mapped["Asset"] = relationship()
    regime: Mapped["MarketRegime | None"] = relationship()


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
