"""Risk Engine — docs/blueprint/08-risk-engine.md#decision-pipeline-do-risk-engine.

The guardian. Has veto power over every signal regardless of its
Opportunity Score — nothing downstream (Execution Engine) may act on a
signal this module has not explicitly approved. Every step below is logged
as a RiskCheck row (whether it passed or not) and the final verdict as one
RiskDecision row, which is what the dashboard's "Why?" panel and the
`/api/risk` endpoint read from — this module never makes an undocumented
decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from packages.portfolio.state import PortfolioState
from packages.risk.config import RiskLimits, load_risk_limits
from packages.risk.correlation_guard import check_correlation_guard
from packages.risk.loss_streak import evaluate_loss_streak
from packages.risk.news_guard import evaluate_news_risk
from packages.risk.position_sizing import calculate_position_size
from packages.risk.safety_belt import evaluate_safety_belt, policy_for, tier_meets_floor
from packages.risk.strategy_health import classify_strategy_health
from packages.shared.models import RiskCheck, StrategyPerformance, SystemState
from packages.shared.models import RiskDecision as RiskDecisionRow

if TYPE_CHECKING:
    # Deferred to type-checking only: packages.risk.advanced_engine imports
    # back through the packages.risk package (`from packages.risk import
    # circuit_breakers`), and packages/risk/__init__.py imports THIS module
    # eagerly -- a module-level import here would be circular. evaluate_signal
    # never constructs or isinstance()-checks this type, only reads attributes
    # off whatever the caller passes, so a type-checking-only import is enough.
    from packages.risk.advanced_engine import AdvancedRiskAssessment

# "PROMPT 12" §100: how long an AdvancedRiskAssessment may be trusted before
# a RiskDecision built from it should be treated as stale -- matches the
# cadence apps/worker is expected to recompute it on (a later task wires
# that cadence in), not a number specific to this module.
RISK_ASSESSMENT_TTL_MINUTES = 15

# "PROMPT 8" §7-11: asset classes where this system can honestly simulate a
# short (cash-settled paper accounting, no borrow/margin mechanics needed —
# packages/execution/order_manager.py's P&L math is already direction-
# symmetric). Real equity short-selling needs borrowed shares/margin this
# system doesn't model at all; rather than silently pretend that away, a
# short signal on an 'equity' asset is honestly blocked (§9: "fallback
# honesto: SHORT=DISABLED se dados insuficientes") instead of simulated as
# if it were the same as a crypto/forex/index/commodity short.
_SHORT_DISABLED_ASSET_CLASSES = {"equity"}


@dataclass(frozen=True)
class SignalForRisk:
    signal_id: int
    asset_id: int
    strategy_id: int
    direction: str
    entry_price: float
    stop_price: float
    target_price: float | None
    risk_reward: float
    confidence: float  # analysis.strength, 0-1
    volatility_factor: float  # >=1.0, see apps/worker/risk_execution.py for how it's derived
    data_quality: str
    data_ts: datetime
    tier: str
    asset_class: str


def _latest_health_score(db: Session, strategy_id: int) -> float | None:
    row = (
        db.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy_id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )
    return row.health_score if row is not None else None


@dataclass(frozen=True)
class RiskCheckOutcome:
    name: str
    passed: bool
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RiskVerdict:
    approved: bool
    approved_quantity: float | None
    reason: str
    safety_belt_level: str
    checks: list[RiskCheckOutcome]


def _persist(
    db: Session, signal_id: int, checks: list[RiskCheckOutcome], *, approved: bool, approved_size: float | None,
    reason: str, belt: str, advanced_risk: AdvancedRiskAssessment | None = None,
) -> None:
    for check in checks:
        db.add(RiskCheck(signal_id=signal_id, check_name=check.name, passed=check.passed, detail=check.detail))
    # "PROMPT 12" §100's richer RiskDecision fields -- all left None when no
    # advanced_risk was supplied (every pre-"PROMPT 12" caller/test), never
    # a fabricated 0/"normal" for a dimension nobody actually assessed.
    drawdown_state = advanced_risk.drawdown.risk_state if advanced_risk and advanced_risk.drawdown else None
    correlation_state = (
        advanced_risk.concentration.concentration_state if advanced_risk and advanced_risk.concentration else None
    )
    model_state = advanced_risk.model_risk.state if advanced_risk and advanced_risk.model_risk else None
    data_state = advanced_risk.data_risk.state if advanced_risk and advanced_risk.data_risk else None
    system_risk_state = advanced_risk.system_risk.state if advanced_risk and advanced_risk.system_risk else None
    expiration = (advanced_risk.ts + timedelta(minutes=RISK_ASSESSMENT_TTL_MINUTES)) if advanced_risk else None

    db.add(
        RiskDecisionRow(
            signal_id=signal_id, approved=approved, approved_size=approved_size, reason=reason, safety_belt_level=belt,
            risk_score=advanced_risk.risk_score if advanced_risk else None,
            risk_state=advanced_risk.risk_state if advanced_risk else None,
            drawdown_state=drawdown_state, correlation_state=correlation_state,
            # liquidity_state/event_state: no dedicated AdvancedRiskEngine
            # dimension for these yet (liquidity has no real orderbook feed
            # -- see step 8 below; event risk is already News Risk Guard's
            # job, step 11) -- left honestly None rather than duplicated.
            liquidity_state=None, event_state=None,
            model_state=model_state, data_state=data_state, system_state=system_risk_state, expiration=expiration,
        )
    )
    db.commit()


def evaluate_signal(
    db: Session,
    signal: SignalForRisk,
    portfolio_state: PortfolioState,
    system_state: SystemState,
    limits: RiskLimits | None = None,
    advanced_risk: AdvancedRiskAssessment | None = None,
) -> RiskVerdict:
    """`advanced_risk` (packages/risk/advanced_engine.py's portfolio-wide
    RiskScore/RiskState) is optional and additive -- "PROMPT 12" §1-15's
    engine feeds richer context into this ALREADY-sovereign pipeline, it
    does not replace any step above. Every caller/test that predates
    "PROMPT 12" (and every call that omits it, e.g. the Critical Safety
    Battery's direct evaluate_signal() calls) gets exactly the pre-"PROMPT
    12" behavior, unchanged.
    """
    limits = limits or load_risk_limits()
    checks: list[RiskCheckOutcome] = []
    belt = evaluate_safety_belt(portfolio_state, limits)
    policy = policy_for(belt, limits)

    def blocked(name: str, detail: dict, reason: str) -> RiskVerdict:
        checks.append(RiskCheckOutcome(name, False, detail))
        _persist(db, signal.signal_id, checks, approved=False, approved_size=None, reason=reason, belt=belt, advanced_risk=advanced_risk)
        return RiskVerdict(False, None, reason, belt, checks)

    def ok(name: str, detail: dict | None = None) -> None:
        checks.append(RiskCheckOutcome(name, True, detail or {}))

    # 1. Kill switch / trading enabled
    if not system_state.trading_enabled:
        return blocked("trading_enabled", {}, "kill_switch")
    ok("trading_enabled")

    # 1b. PAUSE (§60) — a voluntary, reversible operator stop, distinct from
    # the Kill Switch above (an emergency/automatic one). Checked separately
    # so the two read differently downstream: a paused system is NO_TRADE,
    # not EMERGENCY.
    if system_state.trading_paused:
        return blocked("trading_paused", {"reason": system_state.paused_reason}, "trading_paused")
    ok("trading_paused")

    # 1c. TradingMode (§2-4) — this phase never reaches 'live_disabled' in
    # practice (nothing in this codebase writes anything else to
    # trading_mode), but the check is real, not decorative: if it ever did,
    # this is what stops a live order from being sized at all. `None` is
    # treated as the column's own DB-level default ('paper') — a
    # not-yet-flushed SystemState built in-process (tests; the
    # get-or-create path below always commits before this runs) has no
    # ORM-applied default yet, and that is not the same thing as an
    # operator having actually switched modes.
    if system_state.trading_mode not in (None, "paper"):
        return blocked("trading_mode", {"trading_mode": system_state.trading_mode}, "live_trading_disabled")
    ok("trading_mode")

    # 1d. Short-selling honesty fallback (§7-11) — see
    # _SHORT_DISABLED_ASSET_CLASSES above.
    if signal.direction == "short" and signal.asset_class in _SHORT_DISABLED_ASSET_CLASSES:
        return blocked(
            "short_selling_supported",
            {"asset_class": signal.asset_class},
            "short_disabled_insufficient_data",
        )
    ok("short_selling_supported", {"asset_class": signal.asset_class})

    # 1e. Advanced Risk Engine gate ("PROMPT 12" §1-15) -- an ADDITIONAL
    # veto layer for dimensions safety_belt_level alone can't see
    # (correlation concentration, system/execution/model/data risk,
    # DD_LEVEL_4/5 drawdown escalation). Optional: only runs when a caller
    # supplies advanced_risk.
    if advanced_risk is not None:
        if advanced_risk.zero_trade_mode:
            return blocked(
                "advanced_risk_zero_trade_mode",
                {"risk_state": advanced_risk.risk_state, "risk_score": advanced_risk.risk_score, "reasons": advanced_risk.reasons},
                "advanced_risk_zero_trade_mode",
            )
        ok("advanced_risk_zero_trade_mode", {"risk_state": advanced_risk.risk_state})

        if advanced_risk.capital_preservation_mode and not tier_meets_floor(signal.tier, "high_quality"):
            return blocked(
                "advanced_risk_capital_preservation_tier_floor",
                {"tier": signal.tier, "min_tier": "high_quality", "risk_state": advanced_risk.risk_state},
                "advanced_risk_capital_preservation_mode",
            )
        ok(
            "advanced_risk_capital_preservation_tier_floor",
            {"capital_preservation_mode": advanced_risk.capital_preservation_mode},
        )

    # Safety belt policy: does the current belt allow new trades at all, and
    # does this signal's tier clear the belt's floor (docs/blueprint/08-risk-engine.md
    # §Risk States)?
    if not policy.allow_new_trades:
        return blocked("safety_belt_allows_trading", {"belt": belt}, f"safety_belt_{belt}")
    ok("safety_belt_allows_trading", {"belt": belt})

    if not tier_meets_floor(signal.tier, policy.min_tier):
        return blocked("safety_belt_tier_floor", {"tier": signal.tier, "min_tier": policy.min_tier}, "below_safety_belt_tier_floor")
    ok("safety_belt_tier_floor", {"tier": signal.tier, "min_tier": policy.min_tier})

    # 2. Data quality gate
    staleness_seconds = (datetime.now(timezone.utc) - signal.data_ts).total_seconds()
    if signal.data_quality != "high" or staleness_seconds > limits.data_quality.max_staleness_seconds:
        return blocked(
            "data_quality",
            {"data_quality": signal.data_quality, "staleness_seconds": staleness_seconds},
            "data_unavailable",
        )
    ok("data_quality", {"staleness_seconds": round(staleness_seconds, 1)})

    # 3. Risk/reward floor
    if signal.risk_reward < limits.per_trade.min_risk_reward:
        return blocked(
            "risk_reward", {"risk_reward": signal.risk_reward, "min": limits.per_trade.min_risk_reward}, "poor_risk_reward"
        )
    ok("risk_reward", {"risk_reward": signal.risk_reward})

    # 4/5/6. Exposure headroom: portfolio-wide and single-asset
    equity = portfolio_state.equity
    existing_asset_notional = sum(
        p.entry_price * p.size for p in portfolio_state.open_positions if p.asset_id == signal.asset_id
    )
    existing_asset_pct = (existing_asset_notional / equity * 100) if equity > 0 else 0.0
    single_asset_headroom_pct = limits.portfolio.max_single_asset_pct - existing_asset_pct
    if single_asset_headroom_pct <= 0:
        return blocked(
            "single_asset_exposure",
            {"existing_pct": existing_asset_pct, "limit": limits.portfolio.max_single_asset_pct},
            "concentration",
        )
    ok("single_asset_exposure", {"headroom_pct": single_asset_headroom_pct})

    portfolio_headroom_pct = limits.portfolio.max_exposure_pct - portfolio_state.exposure_pct
    if portfolio_headroom_pct <= 0:
        return blocked(
            "portfolio_exposure",
            {"current_pct": portfolio_state.exposure_pct, "limit": limits.portfolio.max_exposure_pct},
            "exposure",
        )
    ok("portfolio_exposure", {"headroom_pct": portfolio_headroom_pct})

    # 7. Correlation guard — uses the tightest headroom so far as the
    # candidate's provisional size share; sizing below re-caps to whatever
    # headroom the guard actually leaves.
    provisional_pct = min(portfolio_headroom_pct, single_asset_headroom_pct)
    guard = check_correlation_guard(db, signal.asset_id, provisional_pct, portfolio_state.open_positions, equity, limits)
    if guard.blocked:
        return blocked(
            "correlation_guard",
            {
                "cluster_exposure_pct": guard.cluster_exposure_pct,
                "limit": limits.portfolio.max_correlated_cluster_pct,
                "correlated_positions": guard.correlated_positions,
            },
            "correlation_guard",
        )
    ok("correlation_guard", {"cluster_exposure_pct": guard.cluster_exposure_pct})
    correlation_headroom_pct = max(0.0, limits.portfolio.max_correlated_cluster_pct - guard.cluster_exposure_pct + provisional_pct)

    # 8. Liquidity / spread — no real orderbook data yet (Phase 2/3 use a
    # mock market data provider with no spread/depth feed). Logged as an
    # explicit pass-through rather than faked as a real check, consistent
    # with docs/blueprint/00-overview.md's "no hallucinated data" rule.
    ok("liquidity", {"note": "spread/orderbook depth check pending a real market data provider"})

    # 9. Daily / weekly / monthly loss limits — equity-based (includes
    # unrealized P&L), not just closed-trade P&L, per docs/blueprint/
    # 08-risk-engine.md.
    if portfolio_state.daily_loss_pct >= limits.loss_limits.max_daily_loss_pct:
        return blocked("daily_loss_limit", {"daily_loss_pct": portfolio_state.daily_loss_pct}, "daily_loss_limit")
    if portfolio_state.weekly_loss_pct >= limits.loss_limits.max_weekly_loss_pct:
        return blocked("weekly_loss_limit", {"weekly_loss_pct": portfolio_state.weekly_loss_pct}, "weekly_loss_limit")
    if portfolio_state.monthly_loss_pct >= limits.loss_limits.max_monthly_loss_pct:
        return blocked("monthly_loss_limit", {"monthly_loss_pct": portfolio_state.monthly_loss_pct}, "monthly_loss_limit")
    ok(
        "loss_limits",
        {
            "daily_loss_pct": portfolio_state.daily_loss_pct,
            "weekly_loss_pct": portfolio_state.weekly_loss_pct,
            "monthly_loss_pct": portfolio_state.monthly_loss_pct,
        },
    )

    # 10. Strategy health — consults packages/quant/learning/strategy_stats.py's
    # health_score (Phase 5). apps/worker/strategy_runner.py already filters
    # lifecycle_stage='quarantine' strategies out before a signal reaches
    # here; "quarantined" below is a defensive second check on the same
    # threshold, not the primary enforcement point.
    health_score = _latest_health_score(db, signal.strategy_id)
    health_verdict = classify_strategy_health(health_score)
    if health_verdict.blocked:
        return blocked(
            "strategy_health",
            {"health_score": health_score, "status": health_verdict.status},
            "strategy_degraded",
        )
    ok("strategy_health", {"health_score": health_score, "status": health_verdict.status})

    # 11. News Risk Guard (Prompt 6 §17/§26) — pre-event macro risk and
    # recent critical/high-importance news. This is the News Intelligence
    # layer's ONLY influence on a trade: a size reduction or a block,
    # exactly like every other check above, never an execution of its own
    # (Prompt 6 §2/§43 — the Risk Engine remains sovereign).
    news_verdict = evaluate_news_risk(db, limits)
    if news_verdict.blocked:
        return blocked(
            "news_risk",
            {"level": news_verdict.level, "reasons": news_verdict.reasons},
            "news_risk_critical",
        )
    ok("news_risk", {"level": news_verdict.level, "reasons": news_verdict.reasons})

    # 12. Loss Streak Detector (§37-39) — a run of losses across the WHOLE
    # portfolio (not just this strategy) only ever reduces size, exactly
    # like every other multiplier here; it never blocks outright (the
    # safety belts already own a full halt at a worse drawdown) and it
    # never increases size on a win streak (§40 anti-martingale —
    # size_multiplier is 1.0 whenever not triggered, full stop).
    loss_streak = evaluate_loss_streak(db, limits.loss_streak)
    ok(
        "loss_streak",
        {"consecutive_losses": loss_streak.consecutive_losses, "triggered": loss_streak.triggered},
    )

    # Advanced Risk Engine size multiplier ("PROMPT 12" §10's DD_LEVEL_1/2
    # "reduce_exposure"/"reduce_new_positions" responses): CAUTION/DEFENSIVE
    # RiskStates reuse the SAME already-configured belt multipliers
    # (config/risk_limits.yaml's safety_belt_multipliers) rather than a
    # second, parallel set of numbers -- these RiskState labels were chosen
    # to match the Safety Belt's own vocabulary at exactly these two levels
    # for this reason. HIGH_RISK and above are already fully handled by the
    # tier-floor/zero_trade_mode gates above (a signal that reaches this
    # point at HIGH_RISK already cleared the high_quality floor), so no
    # further multiplier is needed there.
    advanced_risk_multiplier = 1.0
    if advanced_risk is not None:
        if advanced_risk.risk_state == "caution":
            advanced_risk_multiplier = limits.safety_belt_multipliers.caution
        elif advanced_risk.risk_state == "defensive":
            advanced_risk_multiplier = limits.safety_belt_multipliers.defensive

    # Position sizing — always the smallest of every applicable cap, then
    # scaled down further by the current safety belt's multiplier, the
    # strategy health multiplier, the news risk multiplier, the loss streak
    # multiplier, and (when supplied) the Advanced Risk Engine multiplier.
    sizing = calculate_position_size(
        capital=equity,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
        confidence=signal.confidence,
        volatility_factor=signal.volatility_factor,
        portfolio_headroom_pct=min(portfolio_headroom_pct, single_asset_headroom_pct),
        correlation_headroom_pct=correlation_headroom_pct,
        limits=limits,
    )
    approved_quantity = (
        sizing.quantity
        * policy.size_multiplier
        * health_verdict.size_multiplier
        * news_verdict.size_multiplier
        * loss_streak.size_multiplier
        * advanced_risk_multiplier
    )

    # 13. Leverage ceiling (§41) — a hard assertion, not just a consequence
    # of the caps above: every cap in calculate_position_size() is already
    # expressed as a fraction of `equity` (never of a borrowed/larger
    # number), so notional should structurally never exceed
    # equity * max_leverage. Checked explicitly anyway, the same "prove it,
    # don't just assume it" discipline as every other invariant in this
    # codebase (see e.g. packages/portfolio/reconciliation.py).
    notional = approved_quantity * signal.entry_price
    max_notional = equity * limits.leverage.max_leverage
    if equity > 0 and notional > max_notional * 1.0001:  # tiny float-rounding tolerance, not a policy gap
        return blocked(
            "leverage_ceiling",
            {"notional": notional, "max_notional": max_notional, "max_leverage": limits.leverage.max_leverage},
            "leverage_exceeded",
        )
    ok("leverage_ceiling", {"notional": notional, "max_notional": max_notional})

    if approved_quantity <= 0:
        return blocked("position_sizing", {"sizing": sizing.detail}, "zero_size")
    ok(
        "position_sizing",
        {
            "quantity": approved_quantity,
            "binding_constraint": sizing.binding_constraint,
            "belt_multiplier": policy.size_multiplier,
            "strategy_health_multiplier": health_verdict.size_multiplier,
            "news_risk_multiplier": news_verdict.size_multiplier,
            "advanced_risk_multiplier": advanced_risk_multiplier,
        },
    )

    _persist(
        db, signal.signal_id, checks, approved=True, approved_size=approved_quantity, reason="approved", belt=belt,
        advanced_risk=advanced_risk,
    )
    return RiskVerdict(True, approved_quantity, "approved", belt, checks)
