"""Capital State & Drawdown Engine — "PROMPT 12" §6-15.

CapitalState is a thin extension of packages.portfolio.state.PortfolioState
(the existing single source of truth for cash/equity/exposure/P&L), not a
second computation of the same numbers — see that module's docstring for
the underlying cash/equity accounting this builds on.

DrawdownEngine adds the graduated DD_LEVEL_1..5 response ladder
(config/risk_limits.yaml's drawdown_levels section) that PortfolioState's
own drawdown_pct field doesn't carry any policy for by itself. The ladder's
levels map onto the module-level RiskState vocabulary below — a new,
more granular 7-state composite that sits ALONGSIDE (not replaces)
packages.risk.safety_belt's existing 5-state Safety Belt: the two are
computed independently and can diverge (e.g. a correlation/event spike
pushes RiskState to HIGH_RISK while drawdown itself, and therefore the
Safety Belt, is still NORMAL).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.portfolio.state import PortfolioState, compute_state, get_peak_equity, get_reset_epoch
from packages.risk.config import DrawdownLevelConfig, RiskLimits
from packages.shared.models import PortfolioSnapshot, StrategyPerformance, Trade

# -- RiskState: "PROMPT 12" §8-9's 7-level composite ------------------------
# Deliberately does NOT reuse packages.risk.safety_belt's NORMAL/CAUTION/
# DEFENSIVE/EMERGENCY/KILL_SWITCH string constants even though some names
# overlap — this is a separate vocabulary computed by a separate engine.
# HALTED is reserved for the Kill Switch / a tripped circuit breaker
# (packages/risk/circuit_breakers.py) — DrawdownEngine alone can never
# reach it, only up to EMERGENCY, matching §61-62's "recovery requires a
# human" being a kill-switch-only concern, not an ordinary drawdown one.
NORMAL = "normal"
CAUTION = "caution"
DEFENSIVE = "defensive"
HIGH_RISK = "high_risk"
CRITICAL = "critical"
EMERGENCY = "emergency"
HALTED = "halted"

RISK_STATES = (NORMAL, CAUTION, DEFENSIVE, HIGH_RISK, CRITICAL, EMERGENCY, HALTED)

# Ordered so index i's RiskState is what breaching drawdown_levels.level_{i+1}
# escalates to -- one level number always maps to exactly one RiskState.
_LEVEL_RISK_STATES = (CAUTION, DEFENSIVE, HIGH_RISK, CRITICAL, EMERGENCY)


@dataclass(frozen=True)
class CapitalState:
    """"PROMPT 12" §7's CapitalState. `risk_state` is left None here (it is
    the AdvancedRiskEngine's job to compute and attach the *overall*
    composite once every dimension — not just drawdown — has been
    assessed); pass it in via dataclasses.replace() once known.
    """

    portfolio: PortfolioState
    available_capital: float
    # Always 0.0 this phase -- no margin mechanics, mirrors leverage.max_leverage's
    # existing "PROMPT 8" §41 precedent (paper trading, no borrowed capital).
    margin_used: float
    peak_equity: float
    realized_pnl: float
    risk_state: str | None = None

    @property
    def equity(self) -> float:
        return self.portfolio.equity

    @property
    def cash(self) -> float:
        return self.portfolio.cash

    @property
    def drawdown_pct(self) -> float:
        return self.portfolio.drawdown_pct


def _realized_pnl(db: Session, epoch: datetime | None) -> float:
    query = select(func.coalesce(func.sum(Trade.pnl), 0.0))
    if epoch is not None:
        query = query.where(Trade.closed_at >= epoch)
    return db.execute(query).scalar_one()


def compute_capital_state(db: Session, *, risk_state: str | None = None) -> CapitalState:
    """Pure computation, like packages.portfolio.state.compute_state — does
    not write anything."""
    portfolio = compute_state(db)
    epoch = get_reset_epoch(db)
    return CapitalState(
        portfolio=portfolio,
        available_capital=portfolio.cash,
        margin_used=0.0,
        peak_equity=get_peak_equity(db, portfolio.equity),
        realized_pnl=round(_realized_pnl(db, epoch), 2),
        risk_state=risk_state,
    )


def strategy_drawdown_pct(db: Session, strategy_id: int, portfolio_equity: float) -> float | None:
    """Strategy-level drawdown as a percentage of current portfolio equity
    — honestly None (not 0.0) until the strategy has at least one closed
    trade and thus a StrategyPerformance row (packages/quant/learning/
    strategy_stats.py, refreshed on every position close). Reuses that
    table's already-computed peak-to-trough `max_drawdown` (a currency
    amount over its rolling 200-trade window) rather than re-scanning Trade
    history a second time -- strategies have no separately allocated
    capital pool in this paper-trading model (see packages/portfolio/
    state.py's module docstring), so portfolio equity is the only
    meaningful denominator available to express it as a percentage.
    """
    perf = (
        db.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy_id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )
    if perf is None or perf.max_drawdown is None or portfolio_equity <= 0:
        return None
    return round(perf.max_drawdown / portfolio_equity * 100, 4)


@dataclass(frozen=True)
class DrawdownAssessment:
    drawdown_pct: float  # instantaneous, unadjusted
    effective_drawdown_pct: float  # cooldown/hysteresis-adjusted, >= drawdown_pct
    level: int  # 0 (below level_1) .. 5
    risk_state: str
    response: str  # 'none' or one of drawdown_levels.level_N.response
    recovery_mode: bool  # True while effective_drawdown_pct > drawdown_pct (cooling down)
    threshold_pct: float | None  # the breached level's threshold, None at level 0


def _effective_drawdown_pct(
    db: Session, current_drawdown_pct: float, cooldown_minutes: float, now: datetime, epoch: datetime | None
) -> float:
    """"PROMPT 12" §61's recovery cooldown, implemented as a stateless
    hysteresis over portfolio_snapshots history rather than a new persisted
    "level breached at" timestamp -- the same on-the-fly-from-snapshot-
    history technique packages/portfolio/state.py already uses for its
    weekly/monthly lookback windows. The assessed level can only ever
    de-escalate once the ACTUAL max drawdown over the trailing cooldown
    window (not just the current instant) has fallen below it.
    """
    cutoff = now - timedelta(minutes=cooldown_minutes)
    if epoch is not None and epoch > cutoff:
        cutoff = epoch
    query = select(func.max(PortfolioSnapshot.drawdown_pct)).where(PortfolioSnapshot.ts >= cutoff)
    recent_max = db.execute(query).scalar_one_or_none()
    return max(current_drawdown_pct, recent_max or 0.0)


def _classify_level(effective_drawdown_pct: float, levels: list[DrawdownLevelConfig]) -> tuple[int, str, str]:
    level_num = 0
    risk_state = NORMAL
    response = "none"
    # Walk in increasing-threshold order (load_risk_limits already enforces
    # strictly increasing thresholds) and keep the highest one breached --
    # "PROMPT 12" §9's "nenhum nível inferior pode substituir um nível
    # superior" is structural here: a later (higher) breach always wins.
    for i, lvl in enumerate(levels):
        if effective_drawdown_pct >= lvl.threshold_pct:
            level_num = i + 1
            risk_state = _LEVEL_RISK_STATES[i]
            response = lvl.response
    return level_num, risk_state, response


def assess_drawdown(db: Session, limits: RiskLimits, drawdown_pct: float, *, now: datetime | None = None) -> DrawdownAssessment:
    now = now or datetime.now(timezone.utc)
    epoch = get_reset_epoch(db)
    effective = _effective_drawdown_pct(db, drawdown_pct, limits.recovery.cooldown_minutes, now, epoch)
    level, risk_state, response = _classify_level(effective, limits.drawdown_levels.ordered())
    threshold = limits.drawdown_levels.ordered()[level - 1].threshold_pct if level > 0 else None
    return DrawdownAssessment(
        drawdown_pct=round(drawdown_pct, 4),
        effective_drawdown_pct=round(effective, 4),
        level=level,
        risk_state=risk_state,
        response=response,
        recovery_mode=effective > drawdown_pct,
        threshold_pct=threshold,
    )
