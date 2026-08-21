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
  Post-Phase-7 ("Prompt 2" market data engine): market_events
  Post-Phase-7 ("Prompt 6" news intelligence): macro_events, event_reactions,
    plus the News Intelligence columns added to news_events/news_impact
  Post-Phase-7 ("Prompt 7" backtest lab): backtest_jobs, monte_carlo_runs,
    stress_test_runs
  Post-Phase-7 ("Prompt 8" autonomous paper trading): trading_events,
    system_health, manual_actions, plus TradingMode/pause/idempotency/
    trailing-stop/role columns added to system_state/positions/orders/
    admin_users
  Post-Phase-7 ("Prompt 9" multi-agent quant intelligence): agents,
    agent_messages, agent_predictions, agent_reliability, agent_health,
    decisions, contradictions, plus proposed_by_agent added to
    learned_rules
  Post-Phase-7 ("Prompt 10" autonomous research & evolution): research_hypotheses,
    experiments, strategy_versions, research_approvals, drift_detections,
    research_queue, research_budget_usage, research_knowledge_edges
  Post-Phase-7 ("Prompt 11" global market intelligence): opportunity_clusters,
    anomalies, volatility_events, watchlist_entries, plus metadata/status
    columns added to assets and opportunity_type/fingerprint/expires_at
    added to signals
  Post-Phase-7 ("Prompt 12" advanced risk & capital defense engine):
    risk_config_versions, risk_assessments, plus kill_switch_state/
    recovery_mode/capital_preservation_mode/zero_trade_mode added to
    system_state and risk_score/risk_state/per-dimension-state/expiration
    added to risk_decisions
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
    """Account table — despite the name (kept for migration continuity),
    holds both roles. "PROMPT 8" §84 RBAC: ADMIN can mutate (manual
    controls, kill switch, risk limits, strategy lifecycle); VIEWER can only
    read. Single-tenant in practice (one operator), but the role column
    lets that operator hand out a read-only link without sharing the admin
    password. See docs/blueprint/03-api-spec.md#auth.
    """

    __tablename__ = "admin_users"
    __table_args__ = (CheckConstraint("role IN ('admin','viewer')", name="ck_admin_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Asset(Base):
    """"PROMPT 11" §5 extends asset_class to allow architecture-ready-but-
    not-yet-supported classes (etf/future/bond/option): the column accepts
    them, but no engine in this codebase acts on them yet — a deliberate
    divergence, not a claim of real support.

    `status` (§5's richer ACTIVE/INACTIVE/SUSPENDED/DATA_UNAVAILABLE/
    LOW_LIQUIDITY/QUARANTINED lifecycle) is additive: the existing
    `is_active` boolean is kept untouched as a derived convenience column
    (every current call site that reads it keeps working) and is kept in
    sync wherever `status` is written. `status` is the new source of truth
    going forward.
    """

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "asset_class IN ('crypto','forex','equity','index','commodity','etf','future','bond','option')",
            name="ck_assets_asset_class",
        ),
        CheckConstraint(
            "status IN ('active','inactive','suspended','data_unavailable','low_liquidity','quarantined')",
            name="ck_assets_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    asset_class: Mapped[str] = mapped_column(String, nullable=False)
    exchange: Mapped[str | None] = mapped_column(String)
    base_currency: Mapped[str | None] = mapped_column(String)
    quote_currency: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # -- "PROMPT 11" (global market intelligence) --
    name: Mapped[str | None] = mapped_column(String)
    currency: Mapped[str | None] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String)
    sector: Mapped[str | None] = mapped_column(String)
    industry: Mapped[str | None] = mapped_column(String)
    timezone: Mapped[str | None] = mapped_column(String)
    trading_hours: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    liquidity_score: Mapped[float | None] = mapped_column(Float)
    data_quality_score: Mapped[float | None] = mapped_column(Float)
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


class MarketEvent(Base):
    """Raw market-surveillance events (packages/quant/market/events.py,
    written by apps/worker/scanner.py every scan cycle) — candidates for the
    Pattern/Strategy Engines to later consume, never trades or signals
    themselves. INVALID_MARKET_DATA is included alongside the 7 scanner
    event types (docs/blueprint's "PROMPT 2" spec §7/§10) so both flow
    through one table/API/dashboard panel instead of two side-channels.
    OPPORTUNITY_CREATED (Prompt 3 §26) is emitted by
    apps/worker/strategy_runner.py for signals scoring above 'ignore' —
    PATTERN_DETECTED/REGIME_DETECTED/SIGNAL_CREATED are deliberately not
    emitted here: every strategy/asset pair is scored every cycle (most
    'ignore'-tier), so mirroring each one as a MarketEvent would mostly be
    noise on top of the patterns/market_regimes/signals tables that already
    record every one of them.
    """

    __tablename__ = "market_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('PRICE_MOVEMENT','VOLUME_SPIKE','VOLATILITY_SPIKE',"
            "'BREAKOUT_CANDIDATE','MOMENTUM_CHANGE','TREND_CHANGE','ANOMALY',"
            "'INVALID_MARKET_DATA','OPPORTUNITY_CREATED')",
            name="ck_market_events_event_type",
        ),
        CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_market_events_severity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

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
    __table_args__ = (CheckConstraint("trading_mode IN ('paper','live_disabled')", name="ck_system_state_trading_mode"),)

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
    # Same idea, for the separate apps/backtest_worker process ("PROMPT 7"
    # §46-47) -- a distinct column, not the field above, because the two
    # processes are independently deployed/restarted and conflating their
    # liveness into one timestamp would make either one's outage invisible
    # whenever the other happened to still be healthy.
    backtest_worker_last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # -- "PROMPT 8" Autonomous Paper Trading -------------------------------
    # Explicit TradingMode (§2-4): LIVE is never a reachable value in this
    # phase — there is no code path that writes anything but 'paper' or
    # 'live_disabled', and packages/risk/engine.py's first gate re-checks
    # this on every signal, same as trading_enabled above. See
    # docs/live-trading-non-goal.md.
    trading_mode: Mapped[str] = mapped_column(String, default="paper", nullable=False)
    # PAUSE/RESUME (§60): a voluntary, reversible operator action — distinct
    # from trading_enabled (the Kill Switch, an emergency/automatic stop).
    # Both are checked in packages/risk/engine.py; either one alone blocks
    # new trades, so a paused system reads as NO_TRADE, not EMERGENCY.
    trading_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paused_reason: Mapped[str | None] = mapped_column(Text)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Crash-loop protection for the worker process (§66's "recuperação
    # automática... max_restart_attempts"): apps/worker/main.py increments
    # this on every process start and auto-pauses trading (never touches the
    # Kill Switch — this is an operational safeguard, not a market-risk one)
    # once too many restarts land inside restart_window_started_at's rolling
    # window. Docker's own `restart: unless-stopped` still does the actual
    # OS-level process restart; this only stops a silently crash-looping
    # worker from quietly keeping trading "on" underneath the flapping.
    worker_restart_count: Mapped[int] = mapped_column(default=0, nullable=False)
    restart_window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # RESET PAPER ACCOUNT (§72's manual-control list): when set,
    # packages/portfolio/state.py and packages/portfolio/reconciliation.py
    # both treat this as the start of the account's current life — every
    # PortfolioSnapshot/Order/Trade before it stays in the DB (append-only,
    # never deleted, still fully auditable) but stops counting toward
    # peak-equity/drawdown/cash-reconciliation math, so a reset genuinely
    # starts clean instead of carrying a stale drawdown from a peak that no
    # longer means anything.
    last_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Same idea as backtest_worker_last_heartbeat, for the separate
    # apps/research_worker process ("PROMPT 10" §59's compute isolation —
    # autonomous research never competes with a live scan/strategy/risk
    # cadence OR an operator's own ad-hoc Strategy Lab job for the same
    # reason those two already have independent processes/columns).
    research_worker_last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # -- "PROMPT 12" Advanced Risk & Capital Defense Engine -----------------
    # A richer state machine layered ON TOP of trading_enabled (the Kill
    # Switch boolean stays the sovereign on/off — see packages/risk/
    # circuit_breakers.py's EmergencyKillSwitch), not a replacement for it.
    # 'armed' (normal), 'triggered' (just tripped), 'locked' (tripped and
    # cooling down — no auto-recovery), 'recovery' (a SUPER_ADMIN started
    # the manual recovery review — "PROMPT 12" §61-62: only a human can
    # begin this, and it still requires health review + confirmation before
    # trading_enabled flips back to true).
    kill_switch_state: Mapped[str] = mapped_column(String, default="armed", nullable=False)
    # True only while a SUPER_ADMIN-initiated recovery review is in
    # progress (kill_switch_state == 'recovery'); a plain boolean mirror so
    # callers that only care "are we mid-recovery" don't need to parse the
    # state string.
    recovery_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Set by AdvancedRiskEngine once portfolio RiskState reaches
    # HIGH_RISK/CRITICAL ("PROMPT 12" §10's DD_LEVEL_3/4 responses —
    # highest_quality_only / block_new_trades): position sizing and signal
    # admission both read this, independent of safety_belt_level, since the
    # two composites can diverge (e.g. correlation/event risk high while
    # drawdown itself is still shallow).
    capital_preservation_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Set once RiskState reaches CRITICAL/EMERGENCY or a circuit breaker
    # trips ("PROMPT 12" §66-69): blocks every NEW trade while leaving
    # existing positions to be managed by the ordinary exit/stop machinery
    # (or PositionRiskPolicy's own CLOSE actions) rather than force-closing
    # them the way the Kill Switch's EMERGENCY response does.
    zero_trade_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("severity IN ('info','warning','critical')", name="ck_alerts_severity"),
        CheckConstraint(
            "category IN ('trade','risk','loss','emergency','learning','system','market','news')",
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
    """"PROMPT 11" §12/§17/§27: `Signal` + `OpportunityScore` together are
    already ~90% of the prompt's "Opportunity" object (component-score
    overlap: technical/pattern/regime_fit/historical_edge/liquidity/news/
    risk_reward/strategy_performance/volatility_penalty against the same
    ignore/watch/possible/high_quality/exceptional tiers). Rather than
    create a parallel `Opportunity` table, the few genuinely missing fields
    (closed-vocabulary `opportunity_type`, dedup `fingerprint`, decay
    `expires_at`) are added directly here.
    """

    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint("direction IN ('long','short')", name="ck_signals_direction"),
        CheckConstraint(
            "status IN ('pending','scored','risk_rejected','approved','executed','expired','invalidated')",
            name="ck_signals_status",
        ),
        CheckConstraint(
            "opportunity_type IS NULL OR opportunity_type IN "
            "('breakout','breakdown','trend_continuation','reversal','mean_reversion','momentum',"
            "'volatility_expansion','volatility_compression','relative_strength','relative_weakness',"
            "'event_driven','statistical_arbitrage_candidate')",
            name="ck_signals_opportunity_type",
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
    # -- "PROMPT 11" (global market intelligence) --
    opportunity_type: Mapped[str | None] = mapped_column(String)
    fingerprint: Mapped[str | None] = mapped_column(String, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    # Prompt 3 §17/§20: shown separately from final_score, never as a
    # synonym for it. 0-100 — how much the inputs behind this score can be
    # trusted (data quality, regime confidence, aligned-pattern confidence,
    # whether historical_edge had a real sample), not how good the score is.
    # packages/quant/scoring/inputs.py's compute_opportunity_confidence().
    confidence: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
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
    __table_args__ = (
        UniqueConstraint("signal_id", name="uq_risk_decisions_signal_id"),
        CheckConstraint(
            "risk_state IS NULL OR risk_state IN "
            "('normal','caution','defensive','high_risk','critical','emergency','halted')",
            name="ck_risk_decisions_risk_state",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id"), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approved_size: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    safety_belt_level: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # -- "PROMPT 12" §100's richer RiskDecision object ----------------------
    # All nullable: populated only once AdvancedRiskEngine actually runs
    # (packages/risk/advanced_engine.py, wired in task #140) -- a decision
    # made before that exists (or in a test that only exercises the
    # pre-existing 13-step evaluate_signal pipeline) legitimately has none
    # of this, and NULL says so honestly rather than a fabricated 0/"normal".
    risk_score: Mapped[float | None] = mapped_column(Float)
    risk_state: Mapped[str | None] = mapped_column(String)
    drawdown_state: Mapped[str | None] = mapped_column(String)
    correlation_state: Mapped[str | None] = mapped_column(String)
    liquidity_state: Mapped[str | None] = mapped_column(String)
    event_state: Mapped[str | None] = mapped_column(String)
    model_state: Mapped[str | None] = mapped_column(String)
    data_state: Mapped[str | None] = mapped_column(String)
    system_state: Mapped[str | None] = mapped_column(String)
    # How long this decision's context may be trusted for before it must be
    # re-evaluated rather than reused ("PROMPT 12" §100) -- distinct from
    # Signal.expires_at (Prompt 11), which is about the trading opportunity
    # going stale, not the risk assessment behind an already-approved one.
    expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    signal: Mapped["Signal"] = relationship()


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("direction IN ('long','short')", name="ck_positions_direction"),
        CheckConstraint("status IN ('open','closed')", name="ck_positions_status"),
        CheckConstraint(
            "exit_reason IS NULL OR exit_reason IN ('stop_hit','target_hit','trailing_stop_hit',"
            "'thesis_invalidated','manual_close','kill_switch_close','portfolio_emergency_close',"
            "'reconciliation_pause','regime_change_exit')",
            name="ck_positions_exit_reason",
        ),
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
    # -- "PROMPT 8" trailing stops (§27-29) --------------------------------
    # None => no trailing stop for this position (current_stop is static,
    # the Phase 3 behavior). {"type": "fixed_distance"|"percentage"|
    # "atr_based", "value": float} otherwise — packages/quant/risk/
    # trailing_stop.py reads this each Trade Monitor cycle.
    trailing_stop_config: Mapped[dict | None] = mapped_column(JSON)
    # Best price seen since entry (highest close for a long, lowest for a
    # short) — the anchor a trailing stop measures back from. Distinct from
    # current_stop itself so a trailing stop can only ever ratchet in the
    # trader's favor: current_stop is recomputed from this each cycle, never
    # the other way around.
    favorable_extreme_price: Mapped[float | None] = mapped_column(Float)

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
    # -- "PROMPT 8" duplicate-order protection + execution quality ---------
    # Deterministic per attempt (packages/execution/order_manager.py derives
    # it from signal_id/position_id + a purpose tag, e.g. "open"/"close") —
    # a retried call with the same key hits the unique constraint instead of
    # submitting a second real order (§67-68).
    idempotency_key: Mapped[str | None] = mapped_column(String, unique=True)
    # What the strategy/exit logic expected to pay/receive (signal.entry_price
    # or the position's current_stop/target at exit time) — filled_price
    # above is what actually happened. The gap between the two, not
    # filled_price alone, is what §54's "execution quality" measures.
    expected_price: Mapped[float | None] = mapped_column(Float)
    # Milliseconds between this order being decided (risk-approved / exit
    # condition detected) and submit_order() returning — §54's "latency".
    latency_ms: Mapped[float | None] = mapped_column(Float)


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
    NewsImpact) is the only LLM-touched part of this table pair. The
    columns below `created_at` are "Prompt 6" News Intelligence additions —
    all computed deterministically (packages/quant/news), never by the LLM.
    """

    __tablename__ = "news_events"
    __table_args__ = (
        CheckConstraint(
            "category IN ('central_bank','inflation','employment','gdp','geopolitics',"
            "'regulation','crypto','earnings','m_and_a','interest_rate','cpi','ppi','legal',"
            "'supply_chain','commodity','crypto_regulation','etf','security_breach','banking',"
            "'currency','energy','other')",
            name="ck_news_events_category",
        ),
        CheckConstraint(
            "importance IN ('low','medium','high','critical')", name="ck_news_events_importance"
        ),
        CheckConstraint(
            "sentiment IN ('very_bullish','bullish','neutral','bearish','very_bearish','unknown')",
            name="ck_news_events_sentiment",
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

    # -- "Prompt 6" News Intelligence -------------------------------------
    source_type: Mapped[str | None] = mapped_column(String)
    source_quality_score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    language: Mapped[str] = mapped_column(String, default="en", nullable=False)
    # [{"type": "COMPANY"|"CURRENCY"|"CENTRAL_BANK"|..., "value": "..."}]
    # (packages/quant/news/entities.py) — a curated-dictionary match, never
    # an invented entity ("no hallucinated data" applied to NER too).
    entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # 100 for a genuinely new cluster, decaying toward 0 for near-duplicate
    # repeats of the same event (packages/quant/news/novelty.py).
    novelty_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    # Self-referencing: the id of the earliest event in this item's dedup
    # cluster (packages/quant/news/dedup.py) — equal to `id` for a canonical/
    # unclustered item, so every row always has a cluster to query by.
    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("news_events.id"))
    # 0-100: rises with more independent (distinct-source) members of this
    # item's cluster reporting the same sentiment; distinct from just
    # "N sites copied the same wire story" (Prompt 6 §23).
    source_consensus_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    has_conflicting_sources: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Tone of the headline/body itself (packages/quant/news/sentiment.py, a
    # DET lexicon scorer) — deliberately independent of NewsImpact.direction
    # (the LLM's price-impact call): Prompt 6 §11, "SENTIMENT NÃO É DIREÇÃO".
    sentiment: Mapped[str] = mapped_column(String, default="unknown", nullable=False)
    sentiment_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    importance: Mapped[str] = mapped_column(String, default="low", nullable=False)
    impact_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


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
    # True when the news names this asset (or its issuer) directly; False
    # when the link runs through a sector/macro driver (e.g. a Fed decision
    # affecting NASDAQ) — Prompt 6 §8. Computed by
    # packages/quant/news/asset_mapping.py, independent of the LLM call.
    is_direct: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    news_event: Mapped["NewsEvent"] = relationship(foreign_keys=[news_event_id])
    asset: Mapped["Asset"] = relationship()


class MacroEvent(Base):
    """Scheduled macroeconomic calendar entry — Prompt 6 §15-17.
    packages/data/connectors/macro provides these the same honest-mock way
    packages/data/connectors/{market,news} do; `actual`/`surprise` are only
    ever filled in once the real event has genuinely occurred (§16 —
    "Não assumir automaticamente direção do mercado").
    """

    __tablename__ = "macro_events"
    __table_args__ = (
        CheckConstraint("importance IN ('low','medium','high','critical')", name="ck_macro_events_importance"),
        CheckConstraint("status IN ('scheduled','released')", name="ck_macro_events_status"),
        UniqueConstraint("event", "country", "scheduled_at", name="uq_macro_events_event_country_scheduled_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str | None] = mapped_column(String)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    importance: Mapped[str] = mapped_column(String, nullable=False)
    forecast: Mapped[float | None] = mapped_column(Float)
    previous: Mapped[float | None] = mapped_column(Float)
    actual: Mapped[float | None] = mapped_column(Float)
    surprise: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="scheduled", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EventReaction(Base):
    """Event Reaction Memory (Prompt 6 §19/§30-31): "how does this category
    of event usually move this asset?" — recomputed by
    packages/quant/news/event_reaction.py from real historical price moves
    following past news_events/macro_events, the same rolling-recompute
    pattern as StrategyPerformance (packages/quant/learning/strategy_stats.py).
    `confidence` (not just sample_size) is what gates whether the dashboard/
    scoring ever surfaces this — "só mostrar estatísticas quando a amostra
    for suficiente" (§19).
    """

    __tablename__ = "event_reactions"
    __table_args__ = (UniqueConstraint("event_category", "asset_id", name="uq_event_reactions_category_asset"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_category: Mapped[str] = mapped_column(String, nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    sample_size: Mapped[int] = mapped_column(default=0, nullable=False)
    avg_reaction_pct: Mapped[float | None] = mapped_column(Float)
    positive_rate: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)

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
    # How strong the pattern is vs. how trustworthy its inputs are (Prompt 3
    # §4 — never conflated). packages/quant/indicators/core.py's
    # data_quality_confidence(); 1.0 for pre-existing rows via the migration
    # default, since Phase 1-4 candles were already high-quality by construction.
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
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
    # "PROMPT 9" §31 -- NULL for every rule proposed before the Quant
    # Research Agent existed (packages/agents/specialists/quant_research.py
    # only ever READS this table, it never writes a LearnedRule itself;
    # packages/quant/learning/research.py's run_research_cycle is still the
    # only writer). New rows going forward are tagged so the dashboard can
    # show "proposed by" without guessing on old data.
    proposed_by_agent: Mapped[str | None] = mapped_column(String)


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

    # --- "PROMPT 7" reproducibility (spec §48-49) --------------------------
    # A backtest is reproducible only if every input that could change its
    # result is on record: which strategy/code/data snapshot produced it and
    # (for anything that samples randomly, i.e. Monte Carlo) the exact seed.
    # code_version is the git commit the run executed under -- the one input
    # `params`/`extra_metrics` can't capture on their own.
    strategy_version: Mapped[str | None] = mapped_column(String)
    code_version: Mapped[str | None] = mapped_column(String)
    data_version: Mapped[str | None] = mapped_column(String)
    random_seed: Mapped[int | None] = mapped_column()

    # Every "PROMPT 7" metric beyond the Phase 6 core set (Sortino, recovery
    # factor, gross P&L, exposure, turnover, streaks, drawdown duration,
    # trade distribution, regime breakdown -- packages/backtest/metrics.py)
    # lives here rather than as one column per metric: they're read-only,
    # derived-from-`trades`/`equity_curve` figures with no independent query
    # need of their own, so a JSON bundle avoids ~20 near-permanent nullable
    # columns for numbers every one of which is a pure function of data this
    # row already stores.
    extra_metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    strategy: Mapped["StrategyRow"] = relationship()
    asset: Mapped["Asset"] = relationship()


# --- "PROMPT 7" (Backtesting Engine + Walk-Forward + Monte Carlo + Strategy Lab) --


class BacktestJob(Base):
    """Async job envelope for the heavier "PROMPT 7" analyses (§46-47) —
    Monte Carlo, stress tests, walk-forward optimization and full-lab
    reports can take much longer than a single request/response cycle
    should block on. `kind` picks which engine module
    apps/worker/backtest_jobs.py dispatches to; `payload` is that engine
    call's kwargs (JSON so the schema doesn't grow a column per engine);
    `result` is engine-specific too (references to created BacktestRun ids,
    or, for Monte Carlo/stress test, the run id in monte_carlo_runs/
    stress_test_runs).

    Honest limitation: this worker executes jobs one at a time on a single
    cadence tick (docs/blueprint's established single-process/multiple-
    cadences architecture, not literally-separate OS processes — same
    documented divergence as "PROMPT 6"'s 6 workers). A QUEUED job can be
    cancelled; a RUNNING one runs to completion — there is no mid-job
    interrupt, since the engine call underneath is a plain synchronous
    Python function, not a cooperative/cancellable task.
    """

    __tablename__ = "backtest_jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('backtest','walk_forward','walk_forward_optimization','optimize',"
            "'monte_carlo','stress_test','sensitivity','full_lab')",
            name="ck_backtest_jobs_kind",
        ),
        CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_backtest_jobs_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MonteCarloRun(Base):
    """One Monte Carlo simulation batch (§24-28) over a reference
    BacktestRun's closed trades — never over raw price data, since what's
    being resampled is the trade sequence/return distribution the strategy
    already produced, per §25's four methods."""

    __tablename__ = "monte_carlo_runs"
    __table_args__ = (
        CheckConstraint(
            "method IN ('trade_reshuffling','bootstrap','return_perturbation',"
            "'slippage_perturbation','execution_perturbation')",
            name="ck_monte_carlo_runs_method",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_backtest_run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    num_simulations: Mapped[int] = mapped_column(nullable=False)
    random_seed: Mapped[int] = mapped_column(nullable=False)
    percentiles: Mapped[dict] = mapped_column(JSON, default=dict)
    probability_of_loss: Mapped[float | None] = mapped_column(Float)
    probability_of_drawdown_threshold: Mapped[float | None] = mapped_column(Float)
    drawdown_threshold_pct: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    reference_backtest_run: Mapped["BacktestRun"] = relationship()


class StressTestRun(Base):
    """One stress-test scenario applied to a reference BacktestRun (§29-30,
    §60) — e.g. `volatility_spike`, `slippage_increase`, `market_crash`,
    `kill_switch_drill`. `result` holds the stressed re-run's own metrics
    (same shape as BacktestResult) alongside the delta vs. the reference."""

    __tablename__ = "stress_test_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_backtest_run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), nullable=False)
    scenario: Mapped[str] = mapped_column(String, nullable=False)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    survived: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    reference_backtest_run: Mapped["BacktestRun"] = relationship()


# --- "PROMPT 8" (Autonomous Paper Trading) -------------------------------


class TradingEvent(Base):
    """Event-sourced log of every state-changing moment in the autonomous
    trading loop (§57-59) — the backing store for the "WHY did/didn't the
    system trade?" decision trace and the dashboard's Live Activity Feed.

    Deliberately additive to, not a replacement for, the existing audit
    trail: RiskCheck/RiskDecision already cover *why a signal was
    approved/blocked* in full per-check detail (docs/blueprint/08-risk-engine.md),
    and AuditLog covers admin/system actions (kill switch, quarantine).
    TradingEvent is the one place that stitches moments from *all* of those
    plus order/position lifecycle into a single chronological stream keyed
    by ts, which none of the others are optimized to answer on their own.
    """

    __tablename__ = "trading_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('order_submitted','order_filled','order_rejected',"
            "'position_opened','position_closed','risk_blocked','no_trade',"
            "'trading_paused','trading_resumed','kill_switch_triggered',"
            "'kill_switch_released','reconciliation_mismatch',"
            "'portfolio_emergency_action','loss_streak_detected',"
            "'worker_restarted','crash_loop_protection_triggered')",
            name="ck_trading_events_event_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String)
    entity_id: Mapped[int | None] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemHealth(Base):
    """Periodic health snapshot (§62-66's SystemHealthMonitor) — distinct
    from `GET /api/system/health`'s on-demand computed view: that endpoint
    answers "is the system healthy right now?"; this table answers "was it
    healthy an hour ago?", which nothing else in this schema records over
    time (PortfolioSnapshot tracks money, not health)."""

    __tablename__ = "system_health"
    __table_args__ = (
        CheckConstraint(
            "autonomous_status IN ('starting','running','paused','no_trade',"
            "'caution','defensive','emergency','kill_switch','error')",
            name="ck_system_health_autonomous_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    autonomous_status: Mapped[str] = mapped_column(String, nullable=False)
    trading_mode: Mapped[str] = mapped_column(String, nullable=False)
    trading_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    trading_paused: Mapped[bool] = mapped_column(Boolean, nullable=False)
    safety_belt_level: Mapped[str] = mapped_column(String, nullable=False)
    worker_alive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    open_positions_count: Mapped[int] = mapped_column(nullable=False)
    cadence_failures: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[dict] = mapped_column(JSON, default=dict)


class ManualAction(Base):
    """One row per operator-initiated control action (§68-72's PAUSE/RESUME/
    CLOSE PAPER POSITION/CANCEL PAPER ORDER/ACTIVATE KILL SWITCH/RESET PAPER
    ACCOUNT) with a full before/after snapshot — kept as its own typed table
    rather than folded into AuditLog.detail (used elsewhere in this schema
    for less safety-critical actions) because §72 requires every one of
    these six specifically to carry a structured before/after, not just a
    free-form detail blob, and a dedicated CHECK constraint on `action`
    keeps that list closed and queryable.
    """

    __tablename__ = "manual_actions"
    __table_args__ = (
        CheckConstraint(
            "action IN ('pause','resume','close_position','cancel_order',"
            "'kill_switch','kill_switch_release','reset_paper_account')",
            name="ck_manual_actions_action",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String)
    entity_id: Mapped[int | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)


# -- "PROMPT 9" Multi-Agent Quant Intelligence Architecture ----------------


class Agent(Base):
    """One row per specialist agent. `packages/agents/specialists/__init__.py`'s
    `SPECIALIST_REGISTRY` is the code-side source of truth for which 18
    exist and what each one does; this table is only the runtime state
    (quarantine/enabled) layered on top, upserted from that registry at
    worker startup (`packages/agents/orchestrator.py`) — never the other
    way around.
    """

    __tablename__ = "agents"
    __table_args__ = (CheckConstraint("status IN ('active','quarantined','disabled')", name="ck_agents_status"),)

    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    directional: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version: Mapped[str] = mapped_column(String, default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quarantine_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AgentMessageRow(Base):
    """Persisted history of every `AgentMessage` (`packages/agents/protocol.py`)
    a specialist produced. Distinct Python class name from the dataclass it
    stores — the same "Row" suffix convention already used for
    `packages/risk/engine.py`'s `RiskDecision`/`RiskDecisionRow` pairing.
    """

    __tablename__ = "agent_messages"
    __table_args__ = (
        CheckConstraint("status IN ('ok','unavailable','quarantined')", name="ck_agent_messages_status"),
        CheckConstraint(
            "signal IN ('strong_long','long','neutral','short','strong_short','no_read')",
            name="ck_agent_messages_signal",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_code: Mapped[str] = mapped_column(ForeignKey("agents.code"), nullable=False)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"))
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id"))
    status: Mapped[str] = mapped_column(String, nullable=False)
    signal: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_flags: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentPrediction(Base):
    """One row per directional call a `directional=True` agent makes,
    later settled against real forward price movement
    (`packages/agents/reliability.py::settle_predictions`) — the raw
    material for calibration/overconfidence detection (Prompt 9 §5-6,
    §55-59). Only ever written for a real long/short signal (status=ok,
    signal not in {neutral, no_read}); a NEUTRAL/guardian read has no
    directional claim to grade, so non-directional agents never appear
    here.
    """

    __tablename__ = "agent_predictions"
    __table_args__ = (CheckConstraint("outcome IN ('pending','correct','incorrect')", name="ck_agent_predictions_outcome"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_code: Mapped[str] = mapped_column(ForeignKey("agents.code"), nullable=False)
    agent_message_id: Mapped[int] = mapped_column(ForeignKey("agent_messages.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    predicted_direction: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reference_price: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    evaluate_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    outcome_price: Mapped[float | None] = mapped_column(Float)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentReliability(Base):
    """Rolling calibration snapshot per agent — `packages/agents/reliability.py`'s
    only writer, mirroring `packages/quant/learning/strategy_stats.py`'s
    `StrategyPerformance` shape: one row per `(agent_code, as_of)`, never
    updated in place, so history stays auditable the same way.
    """

    __tablename__ = "agent_reliability"

    agent_code: Mapped[str] = mapped_column(ForeignKey("agents.code"), primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, default=_utcnow)
    sample_size: Mapped[int] = mapped_column(nullable=False)
    correct_count: Mapped[int] = mapped_column(nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Float)
    avg_confidence_when_correct: Mapped[float | None] = mapped_column(Float)
    avg_confidence_when_incorrect: Mapped[float | None] = mapped_column(Float)
    # avg_confidence_when_incorrect - accuracy; positive means the agent is
    # systematically MORE confident on calls it gets wrong than its overall
    # hit rate would justify -- the overconfidence detector Prompt 9 §5 asks for.
    overconfidence_gap: Mapped[float | None] = mapped_column(Float)
    reliability_score: Mapped[float | None] = mapped_column(Float)


class AgentHealth(Base):
    """One row per `(agent_code, cycle)` heartbeat —
    `packages/shared/worker_health.py`'s `SystemHealth` precedent, applied
    per-agent instead of per-process.
    """

    __tablename__ = "agent_health"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_code: Mapped[str] = mapped_column(ForeignKey("agents.code"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)


class Decision(Base):
    """One row per Chief Decision Engine output — one per (asset, worker
    cycle), Prompt 9 §40-46. `agent_inputs` is the full explainability
    trace (Prompt 9's DecisionTrace concept, folded in here rather than a
    parallel table — see docs/multi-agent-architecture.md's deliberate-
    divergence section): every agent's `AgentMessage` as of this decision,
    keyed by agent_code.
    """

    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "decision_state IN ('strong_long_bias','long_bias','neutral','short_bias',"
            "'strong_short_bias','no_trade','blocked')",
            name="ck_decisions_decision_state",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    decision_state: Mapped[str] = mapped_column(String, nullable=False)
    consensus_score: Mapped[float] = mapped_column(Float, nullable=False)
    contradiction_score: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    agent_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    blocked_reason: Mapped[str | None] = mapped_column(String)
    critical_agent_failure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Contradiction(Base):
    """One row per pairwise agent conflict the `ContradictionEngine`
    flagged for this decision — `packages/agents/contradiction.py`'s only
    writer.
    """

    __tablename__ = "contradictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), nullable=False)
    agent_code_a: Mapped[str] = mapped_column(String, nullable=False)
    agent_code_b: Mapped[str] = mapped_column(String, nullable=False)
    signal_a: Mapped[str] = mapped_column(String, nullable=False)
    signal_b: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


# -- "PROMPT 10" Autonomous Research & Evolution Engine --------------------


class ResearchHypothesis(Base):
    """A testable research question — "PROMPT 10" §11-14. Distinct from
    `LearnedRule` (Phase 5): a `LearnedRule` is a narrow rule-condition
    artifact from `packages/quant/learning/research.py`'s existing DET+LLM
    pipeline; a `ResearchHypothesis` is the broader "why is this strategy
    struggling and what might fix it" research question this phase's
    `AutonomousResearchAgent` reasons over, with its own approval workflow
    (`ResearchApproval`) and full experiment lifecycle. The two are not
    merged — different granularity, different consumers.
    """

    __tablename__ = "research_hypotheses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed','approved','rejected','request_more_tests','experimenting','completed')",
            name="ck_research_hypotheses_status",
        ),
        CheckConstraint("risk IN ('low','medium','high')", name="ck_research_hypotheses_risk"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    expected_effect: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(String, default="medium", nullable=False)
    assets: Mapped[list] = mapped_column(JSON, default=list)
    timeframes: Mapped[list] = mapped_column(JSON, default=list)
    regimes: Mapped[list] = mapped_column(JSON, default=list)
    # "PROMPT 10" §4: which research trigger produced this (strategy_
    # degradation/regime_change/agent_disagreement/anomaly/manual/...).
    source: Mapped[str] = mapped_column(String, nullable=False)
    # §14/§15's quality/priority dimensions, kept as one JSON blob rather
    # than six columns -- they're always read/written together and never
    # individually queried/filtered on.
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    priority_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="proposed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Experiment(Base):
    """Control vs candidate comparison — "PROMPT 10" §16-21. The engine
    behind this is `packages/backtest/report.py::run_full_lab`, called once
    for `control` and once for `candidate` — this table never re-implements
    backtesting, it records what was compared and the result of comparing
    it. `status` is the exact closed vocabulary from §20.
    """

    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(
            "type IN ('backtest','walk_forward','optimization','feature_test','strategy_test',"
            "'regime_test','event_test','genetic_search','ablation')",
            name="ck_experiments_type",
        ),
        CheckConstraint(
            "status IN ('queued','running','completed','failed','rejected','promising',"
            "'validating','approved','quarantined')",
            name="ck_experiments_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hypothesis_id: Mapped[int | None] = mapped_column(ForeignKey("research_hypotheses.id"))
    type: Mapped[str] = mapped_column(String, nullable=False)
    control: Mapped[dict] = mapped_column(JSON, nullable=False)
    candidate: Mapped[dict] = mapped_column(JSON, nullable=False)
    dataset: Mapped[dict] = mapped_column(JSON, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    # §89 reproducibility: code_version/random_seed/environment/timestamp —
    # one JSON blob, same reasoning as ResearchHypothesis.quality above.
    reproducibility: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StrategyVersion(Base):
    """One parameterized/DSL variant of a strategy — "PROMPT 10" §26-29,
    §65-70. `StrategyRow` (Phase 2) stays the one row per named strategy
    *code*; this is the new, orthogonal axis: many versions can exist per
    `strategy_id`, each independently validated and independently a
    CHAMPION/CHALLENGER/EXPERIMENTAL/etc. Never touches
    `StrategyRow.lifecycle_stage` (idea/.../production — the capital-tier
    promotion axis, "PROMPT 6"/Phase 6, untouched by this phase).
    """

    __tablename__ = "strategy_versions"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN ('experimental','challenger','champion','production_candidate','rolled_back','retired')",
            name="ck_strategy_versions_lifecycle_status",
        ),
        CheckConstraint(
            "validation_status IN ('EXPERIMENTAL','PROMISING','VALIDATING','ROBUST','DEGRADED','REJECTED','QUARANTINED')",
            name="ck_strategy_versions_validation_status",
        ),
        UniqueConstraint("strategy_id", "version", name="uq_strategy_versions_strategy_id_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    parent_version_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_versions.id"))
    changes: Mapped[list] = mapped_column(JSON, default=list)
    dsl_definition: Mapped[dict | None] = mapped_column(JSON)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    performance: Mapped[dict] = mapped_column(JSON, default=dict)
    # Reuses packages/backtest/quality_score.py's exact closed STATUS_LABELS
    # set — one source of truth for what these labels mean, not a second
    # vocabulary that could silently drift from the one the Strategy Lab
    # dashboard already displays.
    validation_status: Mapped[str] = mapped_column(String, default="EXPERIMENTAL", nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String, default="experimental", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_by: Mapped[str] = mapped_column(String, nullable=False)


class ResearchApproval(Base):
    """Human-in-the-loop review — "PROMPT 10" §82-85. One row per review
    action (approve/reject/request_more_tests/promote/rollback/quarantine)
    against a hypothesis/strategy_version/experiment, mirroring
    `ManualAction`'s before/after audit-trail precedent ("PROMPT 8").
    `entity_type`/`entity_id` is a loose reference (no FK — spans several
    tables) exactly like `AuditLog`'s existing pattern.
    """

    __tablename__ = "research_approvals"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('hypothesis','strategy_version','experiment')", name="ck_research_approvals_entity_type"
        ),
        CheckConstraint(
            "action IN ('approve','reject','request_more_tests','promote','rollback','quarantine')",
            name="ck_research_approvals_action",
        ),
        CheckConstraint(
            "status IN ('pending_review','approved','rejected','request_more_tests')",
            name="ck_research_approvals_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending_review", nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DriftDetection(Base):
    """One row per detected distribution shift — "PROMPT 10" §71-74.
    Detecting drift never modifies production by itself (§73-74): the only
    consequence is a row here plus, at the caller's discretion, a new
    `ResearchHypothesis` proposing an adaptation to investigate.
    """

    __tablename__ = "drift_detections"
    __table_args__ = (
        CheckConstraint("drift_type IN ('feature','market','strategy','agent','data')", name="ck_drift_detections_drift_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    drift_type: Mapped[str] = mapped_column(String, nullable=False)
    entity: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String, nullable=False)


class ResearchQueueItem(Base):
    """Async job envelope for autonomous research workloads — "PROMPT 10"
    §58-61. Same pattern as `BacktestJob` ("PROMPT 7"), deliberately a
    separate table/queue/worker process (`apps/research_worker/`) rather
    than added `kind`s on `BacktestJob`: research jobs carry a different
    payload shape (hypothesis linkage, budget tracking) and must never
    compete with a human-triggered ad-hoc Strategy Lab job for the same
    queue (§59 compute isolation — research must never degrade market/risk
    monitoring OR an operator's own on-demand backtest).
    """

    __tablename__ = "research_queue"
    __table_args__ = (
        CheckConstraint(
            "queue_type IN ('hypothesis','experiment','feature_test','strategy_test',"
            "'regime_test','event_test','knowledge_update')",
            name="ck_research_queue_queue_type",
        ),
        CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_research_queue_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    queue_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResearchBudgetUsage(Base):
    """One row per unit of research compute spent — "PROMPT 10" §56-57.
    `packages/research/budget.py::check_budget` sums today's rows per
    `resource_type` against `config/research_budget.yaml`'s limits before
    letting a new job queue — never after the fact.
    """

    __tablename__ = "research_budget_usage"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('experiment','backtest','llm_call','api_call')", name="ck_research_budget_usage_resource_type"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("experiments.id"))


class ResearchKnowledgeEdge(Base):
    """One relationship in the research knowledge graph — "PROMPT 10"
    §42-43 (e.g. "BREAKOUT works_well_in HIGH_VOLUME"). Populated only from
    statistically-evidenced experiment/regime-breakdown results
    (`sample_size`/`confidence` always recorded) — never a bare assertion,
    per §44's "exigir validação estatística".
    """

    __tablename__ = "research_knowledge_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    relation: Mapped[str] = mapped_column(String, nullable=False)
    object: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    source_experiment_id: Mapped[int | None] = mapped_column(ForeignKey("experiments.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# -- "PROMPT 11" Global Market Intelligence & 24/7 Opportunity Discovery ----
#
# Deliberately only 4 new tables (+ the Asset/Signal ALTERs above). Most of
# the prompt's "Data Storage" list (§89: MarketUniverse/Asset/MarketSnapshot/
# ScanResult/Opportunity/OpportunityEvidence/EconomicEvent/MarketRegime/
# VolatilityState/MarketAlert) already exists (Asset/OHLCV/Signal+
# OpportunityScore/MacroEvent/MarketRegime/Alert respectively) or is a cheap
# pure function that doesn't need persistence (MarketSession — see
# packages/market/sessions.py). A persisted `ScanResult` table was
# deliberately rejected: unbounded per-scan-cycle growth with no retention
# story, and every scan's output already lands in Signal/OpportunityScore
# (the durable record) or nowhere (a rejected candidate, honestly discarded).


class OpportunityCluster(Base):
    """A group of correlated same-direction opportunities detected together
    (e.g. BTC/ETH/SOL longs) — "PROMPT 11" §33-35. Reuses
    `packages/risk/correlation_guard.py::refresh_correlation_matrix`'s
    output rather than computing correlation again. Evidence for a combined-
    risk penalty applied at ranking time (`packages/market/ranking.py`), not
    a claim of a causal relationship between the clustered assets.
    """

    __tablename__ = "opportunity_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    signal_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    asset_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    factor: Mapped[str | None] = mapped_column(String)
    avg_correlation: Mapped[float] = mapped_column(Float, nullable=False)
    combined_risk: Mapped[float] = mapped_column(Float, nullable=False)
    ranking_penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    __table_args__ = (
        CheckConstraint("direction IN ('long','short')", name="ck_opportunity_clusters_direction"),
    )


class Anomaly(Base):
    """An unusual price/volume/volatility/spread/correlation/news move —
    "PROMPT 11" §45-49. Reuses `packages/quant/patterns/detector.py`'s
    `detect_anomaly`/`detect_cross_asset` z-score primitives; this table
    adds only the persisted 0-100 `AnomalyScore` and review status.

    An anomaly is explicitly NOT a trade signal — see the module docstring
    in `packages/market/anomaly.py`: "an anomaly means INVESTIGATE, not
    TRADE." `reviewed`/`explanation` exist so a human (or a later research
    cycle) can record what a flagged anomaly turned out to be, never so the
    system auto-trades it.
    """

    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    anomaly_type: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)

    asset: Mapped["Asset"] = relationship()

    __table_args__ = (
        CheckConstraint(
            "anomaly_type IN ('price_move','volume_spike','volatility_spike','spread_expansion',"
            "'correlation_breakdown','news_shock')",
            name="ck_anomalies_anomaly_type",
        ),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_anomalies_score_range"),
    )


class VolatilityEvent(Base):
    """A compression/expansion/spike/collapse transition in an asset's
    volatility regime — "PROMPT 11" §54-57. Reuses
    `packages/quant/indicators/core.py::atr`/`realized_volatility` for the
    underlying measurement; this table adds only the percentile ranking and
    the persisted regime-transition record.
    """

    __tablename__ = "volatility_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    realized_vol: Mapped[float] = mapped_column(Float, nullable=False)
    percentile: Mapped[float] = mapped_column(Float, nullable=False)
    regime: Mapped[str] = mapped_column(String, nullable=False)

    asset: Mapped["Asset"] = relationship()

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('compression','expansion','spike','collapse')",
            name="ck_volatility_events_event_type",
        ),
        CheckConstraint(
            "regime IN ('low','normal','high','extreme')",
            name="ck_volatility_events_regime",
        ),
    )


class WatchlistEntry(Base):
    """The Dynamic Watchlist — "PROMPT 11" §77-79. One row per asset
    (re-triggering an already-active entry updates `reason`/`updated_at`
    in place rather than inserting a duplicate). Removed, not deleted, so
    `removal_reason` stays available for the Discovery Memory feedback loop
    (§85-86).
    """

    __tablename__ = "watchlist_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str | None] = mapped_column(String)

    asset: Mapped["Asset"] = relationship()

    __table_args__ = (
        CheckConstraint(
            "reason IN ('anomaly','news','volume','volatility','opportunity','manual')",
            name="ck_watchlist_entries_reason",
        ),
        CheckConstraint("status IN ('active','removed')", name="ck_watchlist_entries_status"),
        CheckConstraint(
            "removal_reason IS NULL OR removal_reason IN "
            "('opportunity_disappeared','liquidity_deterioration','data_quality_deterioration','manual')",
            name="ck_watchlist_entries_removal_reason",
        ),
    )


# -- "PROMPT 12" Advanced Risk & Capital Defense Engine ---------------------
#
# Deliberately only 2 new tables (+ the SystemState/RiskDecision ALTERs
# above). This phase is mostly a new orchestration/aggregation layer over
# already very rich existing risk infrastructure (the sovereign 13-step
# packages/risk/engine.py::evaluate_signal pipeline, the 5-level Safety
# Belt, the Loss Streak Detector, the Kill Switch, Position Risk Policy,
# and Prompt 7/9's Monte Carlo/Risk-of-Ruin/consensus/contradiction
# primitives) -- see docs/capital-defense-engine.md for the full map of
# what "PROMPT 12" asks for vs. what already existed before it started.


class RiskConfigVersion(Base):
    """One row per change to a risk limit/threshold — "PROMPT 12" §116-119:
    every edit to config/risk_limits.yaml's live-tunable values (drawdown
    levels, loss-streak thresholds, correlation caps, ...) must be
    versioned and auditable, never a silent in-place file edit. `version`
    is a simple incrementing sequence (not the row `id`, so a future
    rollback can re-point "current" at an older version without renumbering
    history). `parameters` holds the full resolved config snapshot after
    the change, not just the diff, so any version can be inspected or
    restored on its own without replaying history.
    """

    __tablename__ = "risk_config_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','active','superseded','rejected')",
            name="ck_risk_config_versions_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)


class RiskAssessment(Base):
    """An append-only portfolio-wide risk snapshot, one row per
    AdvancedRiskEngine pass — "PROMPT 12" §100/§107-108 (the Risk Event
    Timeline and periodic risk reports read this table's history). Distinct
    from `risk_decisions` (one row per *signal*, written only when a signal
    is evaluated): this table is written on every engine cycle regardless
    of whether any signal arrived, so a quiet market still has a continuous
    risk-state history to look back on.
    """

    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_state: Mapped[str] = mapped_column(String, nullable=False)
    drawdown_state: Mapped[str | None] = mapped_column(String)
    correlation_state: Mapped[str | None] = mapped_column(String)
    liquidity_state: Mapped[str | None] = mapped_column(String)
    volatility_state: Mapped[str | None] = mapped_column(String)
    event_state: Mapped[str | None] = mapped_column(String)
    model_state: Mapped[str | None] = mapped_column(String)
    data_state: Mapped[str | None] = mapped_column(String)
    system_state: Mapped[str | None] = mapped_column(String)
    execution_state: Mapped[str | None] = mapped_column(String)
    capital_preservation_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    zero_trade_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, default=list)

    __table_args__ = (
        CheckConstraint(
            "risk_state IN ('normal','caution','defensive','high_risk','critical','emergency','halted')",
            name="ck_risk_assessments_risk_state",
        ),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_risk_assessments_risk_score_range"),
    )
