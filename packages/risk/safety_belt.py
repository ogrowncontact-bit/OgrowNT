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
    # 0.7x, not the full daily-loss limit: packages/risk/engine.py's loss_limits
    # check hard-blocks every new trade once daily_loss_pct reaches 100% of
    # max_daily_loss_pct, so triggering DEFENSIVE at that same 100% would make
    # its "reduce size, require high_quality+" action dead code -- it would
    # always coincide with the hard block. The 70% warning zone (same fraction
    # CAUTION already uses for weekly loss) gives DEFENSIVE genuine room to
    # actually reduce risk before the hard stop, matching Prompt 4's "cada
    # estado com ações diferentes" requirement.
    if state.daily_loss_pct >= limits.loss_limits.max_daily_loss_pct * 0.7:
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

# Opportunity-tier floor and new-trade permission per belt level. The risk
# multiplier itself is NOT here — it comes from limits.safety_belt_multipliers
# (config/risk_limits.yaml), operator-tunable per Prompt 4 §35, unlike these
# two which are structural behavior rather than a risk-limit number.
_POLICY_META: dict[str, tuple[str, bool]] = {
    NORMAL: ("possible", True),
    CAUTION: ("possible", True),
    DEFENSIVE: ("high_quality", True),
    EMERGENCY: ("exceptional", False),
    KILL_SWITCH: ("exceptional", False),
}


def policy_for(level: str, limits: RiskLimits) -> SafetyBeltPolicy:
    min_tier, allow_new_trades = _POLICY_META.get(level, _POLICY_META[NORMAL])
    # Field names on SafetyBeltMultipliersConfig match the belt-level string
    # constants exactly, so this is a direct attribute read, not a dict
    # lookup that could silently fall through to a default.
    multiplier = getattr(limits.safety_belt_multipliers, level, limits.safety_belt_multipliers.normal)
    return SafetyBeltPolicy(size_multiplier=multiplier, min_tier=min_tier, allow_new_trades=allow_new_trades)


def tier_meets_floor(tier: str, min_tier: str) -> bool:
    return _TIER_RANK.get(tier, 0) >= _TIER_RANK.get(min_tier, 99)
