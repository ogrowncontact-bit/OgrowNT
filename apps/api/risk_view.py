"""Shared RiskDecision -> API view derivation — used by both
apps/api/routers/risk.py (GET /api/risk) and apps/api/routers/trading.py
(the position "Why?" panel), so the two never drift on how decision/reasons/
risk_amount are derived from the same persisted RiskCheck rows.
"""
from __future__ import annotations

from packages.shared.models import RiskCheck, Signal


def derive_decision_view(
    *, approved: bool, reason: str, approved_size: float | None, checks: list[RiskCheck], signal: Signal
) -> dict:
    """Prompt 4 §25/26: a structured decision + reasons list + risk_amount/
    position_size/risk_reward, derived entirely from what evaluate_signal()
    already persisted (packages/risk/engine.py) — no new columns, same
    approach as Prompt 3's evidence/confidence API-layer enrichment.
    """
    by_name = {c.check_name: c for c in checks}
    risk_reward_check = by_name.get("risk_reward")
    risk_reward = risk_reward_check.detail.get("risk_reward") if risk_reward_check else None

    if not approved:
        return {
            "decision": "blocked",
            "reasons": [reason],
            "risk_amount": None,
            "position_size": None,
            "risk_reward": risk_reward,
        }

    sizing_check = by_name.get("position_sizing")
    detail = sizing_check.detail if sizing_check else {}
    belt_multiplier = detail.get("belt_multiplier", 1.0)
    health_multiplier = detail.get("strategy_health_multiplier", 1.0)
    news_risk_multiplier = detail.get("news_risk_multiplier", 1.0)

    reduction_reasons = []
    if belt_multiplier < 1.0:
        reduction_reasons.append("safety_belt_size_reduction")
    if health_multiplier < 1.0:
        reduction_reasons.append("strategy_health_size_reduction")
    if news_risk_multiplier < 1.0:
        reduction_reasons.append("news_risk_size_reduction")

    risk_amount = approved_size * abs(signal.entry_price - signal.stop_price) if approved_size is not None else None

    return {
        "decision": "reduced" if reduction_reasons else "approved",
        "reasons": reduction_reasons,
        "risk_amount": risk_amount,
        "position_size": approved_size,
        "risk_reward": risk_reward,
    }
