"""SQLAlchemy models — Phase 1 subset of docs/blueprint/02-database-schema.md.

Only the tables needed to satisfy the Phase 1 acceptance criteria are defined
here (auth, assets, OHLCV, paper portfolio, system state, alerts, audit log).
Tables for later phases (news, patterns, regimes, strategies, signals, risk
decisions, positions/orders/trades, memory, learning) are specified in the
blueprint and will be added, table by table, as each phase is implemented —
not stubbed out in advance.
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
