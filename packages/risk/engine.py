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
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.portfolio.state import PortfolioState
from packages.risk.config import RiskLimits, load_risk_limits
from packages.risk.correlation_guard import check_correlation_guard
from packages.risk.position_sizing import calculate_position_size
from packages.risk.safety_belt import evaluate_safety_belt, policy_for, tier_meets_floor
from packages.shared.models import RiskCheck, RiskDecision as RiskDecisionRow, SystemState


@dataclass(frozen=True)
class SignalForRisk:
    signal_id: int
    asset_id: int
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


def _persist(db: Session, signal_id: int, checks: list[RiskCheckOutcome], *, approved: bool, approved_size: float | None, reason: str, belt: str) -> None:
    for check in checks:
        db.add(RiskCheck(signal_id=signal_id, check_name=check.name, passed=check.passed, detail=check.detail))
    db.add(
        RiskDecisionRow(
            signal_id=signal_id, approved=approved, approved_size=approved_size, reason=reason, safety_belt_level=belt
        )
    )
    db.commit()


def evaluate_signal(
    db: Session,
    signal: SignalForRisk,
    portfolio_state: PortfolioState,
    system_state: SystemState,
    limits: RiskLimits | None = None,
) -> RiskVerdict:
    limits = limits or load_risk_limits()
    checks: list[RiskCheckOutcome] = []
    belt = evaluate_safety_belt(portfolio_state, limits)
    policy = policy_for(belt)

    def blocked(name: str, detail: dict, reason: str) -> RiskVerdict:
        checks.append(RiskCheckOutcome(name, False, detail))
        _persist(db, signal.signal_id, checks, approved=False, approved_size=None, reason=reason, belt=belt)
        return RiskVerdict(False, None, reason, belt, checks)

    def ok(name: str, detail: dict | None = None) -> None:
        checks.append(RiskCheckOutcome(name, True, detail or {}))

    # 1. Kill switch / trading enabled
    if not system_state.trading_enabled:
        return blocked("trading_enabled", {}, "kill_switch")
    ok("trading_enabled")

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

    # 9. Daily / weekly loss limits
    if portfolio_state.daily_loss_pct >= limits.loss_limits.max_daily_loss_pct:
        return blocked("daily_loss_limit", {"daily_loss_pct": portfolio_state.daily_loss_pct}, "daily_loss_limit")
    if portfolio_state.weekly_loss_pct >= limits.loss_limits.max_weekly_loss_pct:
        return blocked("weekly_loss_limit", {"weekly_loss_pct": portfolio_state.weekly_loss_pct}, "weekly_loss_limit")
    ok("loss_limits", {"daily_loss_pct": portfolio_state.daily_loss_pct, "weekly_loss_pct": portfolio_state.weekly_loss_pct})

    # 10. Strategy drawdown — no closed-trade history yet per strategy
    # (Strategy Memory arrives Phase 5). Same honest pass-through as liquidity.
    ok("strategy_drawdown", {"note": "strategy performance tracking pending Phase 5"})

    # Position sizing — always the smallest of every applicable cap, then
    # scaled down further by the current safety belt's multiplier.
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
    approved_quantity = sizing.quantity * policy.size_multiplier

    if approved_quantity <= 0:
        return blocked("position_sizing", {"sizing": sizing.detail}, "zero_size")
    ok(
        "position_sizing",
        {"quantity": approved_quantity, "binding_constraint": sizing.binding_constraint, "belt_multiplier": policy.size_multiplier},
    )

    _persist(db, signal.signal_id, checks, approved=True, approved_size=approved_quantity, reason="approved", belt=belt)
    return RiskVerdict(True, approved_quantity, "approved", belt, checks)
