"""Position Risk Policy — "PROMPT 8" §28-30.

An open position is never closed or reduced unilaterally by whichever
module first noticed a problem: a strategy's worst-regime shift, a critical
news event, or a portfolio emergency (Kill Switch / max drawdown) all
route through this module before anything touches the position. This is
still the Risk Engine's call, not the News Engine's or the Trade Monitor's
own (§29: "Nunca permitir que News Engine feche diretamente"). The action
per trigger is a config value (config/risk_limits.yaml's
position_risk_policy), never a hardcoded guess (§30: "Não implementar
comportamento implícito").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from packages.risk.config import RiskLimits

TriggerType = Literal["regime_change", "news_risk", "portfolio_emergency"]
PolicyAction = Literal["hold", "reduce", "close"]


@dataclass(frozen=True)
class PositionRiskDecision:
    action: PolicyAction
    trigger: TriggerType
    reason: str


def evaluate_position_risk_event(trigger: TriggerType, *, limits: RiskLimits, detail: str) -> PositionRiskDecision:
    action = getattr(limits.position_risk_policy, trigger)
    if action not in ("hold", "reduce", "close"):
        # An invalid config value fails safe toward the more conservative
        # action rather than silently doing nothing — a typo in the YAML
        # must never turn into an unnoticed HOLD.
        action = "close"
    return PositionRiskDecision(action=action, trigger=trigger, reason=detail)
