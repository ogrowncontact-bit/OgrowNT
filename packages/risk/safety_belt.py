"""Safety Belts — docs/blueprint/08-risk-engine.md#risk-states-safety-belts.

Pure state evaluation from portfolio metrics — the caller (apps/worker) is
responsible for persisting the result to system_state and publishing
RISK_STATE_CHANGED. Kill Switch is intentionally NOT triggered automatically
by evaluate_safety_belt (EMERGENCY is its ceiling) — see
should_trigger_kill_switch, kept separate because tripping it is a much
bigger deal (stops all new trading) and the caller must log why explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.portfolio.state import PortfolioState
from packages.risk.config import RiskLimits

NORMAL = "normal"
CAUTION = "caution"
DEFENSIVE = "defensive"
EMERGENCY = "emergency"
KILL_SWITCH = "kill_switch"


def evaluate_safety_belt(state: PortfolioState, limits: RiskLimits) -> str:
    if state.drawdown_pct >= limits.loss_limits.max_portfolio_drawdown_pct:
        return EMERGENCY
    if state.daily_loss_pct >= limits.loss_limits.max_daily_loss_pct:
        return DEFENSIVE
    if state.weekly_loss_pct >= limits.loss_limits.max_weekly_loss_pct * 0.7:
        return CAUTION
    return NORMAL


def should_trigger_kill_switch(state: PortfolioState, limits: RiskLimits) -> bool:
    """Automatic Kill Switch trigger — docs/blueprint/08-risk-engine.md#kill-switch:
    drawdown > 1.5x the EMERGENCY threshold in the current tracking window.
    Deliberately conservative (well past EMERGENCY) so it only fires for a
    genuinely severe, unambiguous situation, not a slightly-worse-than-usual day.
    """
    return state.drawdown_pct >= limits.loss_limits.max_portfolio_drawdown_pct * 1.5


@dataclass(frozen=True)
class SafetyBeltPolicy:
    size_multiplier: float
    min_tier: str  # opportunity tier floor eligible for consideration at this belt level
    allow_new_trades: bool


_TIER_RANK = {"ignore": 0, "watch": 1, "possible": 2, "high_quality": 3, "exceptional": 4}

_POLICIES: dict[str, SafetyBeltPolicy] = {
    NORMAL: SafetyBeltPolicy(size_multiplier=1.0, min_tier="possible", allow_new_trades=True),
    CAUTION: SafetyBeltPolicy(size_multiplier=0.75, min_tier="possible", allow_new_trades=True),
    DEFENSIVE: SafetyBeltPolicy(size_multiplier=0.5, min_tier="high_quality", allow_new_trades=True),
    EMERGENCY: SafetyBeltPolicy(size_multiplier=0.0, min_tier="exceptional", allow_new_trades=False),
    KILL_SWITCH: SafetyBeltPolicy(size_multiplier=0.0, min_tier="exceptional", allow_new_trades=False),
}


def policy_for(level: str) -> SafetyBeltPolicy:
    return _POLICIES.get(level, _POLICIES[NORMAL])


def tier_meets_floor(tier: str, min_tier: str) -> bool:
    return _TIER_RANK.get(tier, 0) >= _TIER_RANK.get(min_tier, 99)
