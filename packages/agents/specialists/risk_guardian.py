"""Risk Guardian Agent — "PROMPT 9" §33, one of CRITICAL_AGENT_CODES.

An ADVISORY read of the same safety-belt/loss-streak state the real
sovereign Risk Engine (`packages/risk/engine.py`) independently re-computes
and enforces on every single signal — this agent never gates anything
itself (see `packages/agents/permissions.py` and
`tests/test_agent_sandbox.py`'s structural proof). Its purpose is honesty,
not authority: the multi-agent layer's own view of risk state should never
silently diverge from what the Risk Engine is actually about to do.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.portfolio.state import compute_state
from packages.risk.config import load_risk_limits
from packages.risk.loss_streak import evaluate_loss_streak
from packages.risk.safety_belt import NORMAL, evaluate_safety_belt, policy_for

AGENT_CODE = "risk_guardian"


def analyze(ctx: AgentContext) -> AgentMessage:
    limits = load_risk_limits()
    state = compute_state(ctx.db)
    belt = evaluate_safety_belt(state, limits)
    policy = policy_for(belt, limits)
    loss_streak = evaluate_loss_streak(ctx.db, limits.loss_streak)

    risk_flags = []
    if belt != NORMAL:
        risk_flags.append(f"safety_belt_{belt}")
    if not policy.allow_new_trades:
        risk_flags.append("new_trades_blocked_by_belt")
    if loss_streak.triggered:
        risk_flags.append("loss_streak_active")

    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=1.0,
        evidence={
            "safety_belt": belt, "allow_new_trades": policy.allow_new_trades, "min_tier": policy.min_tier,
            "consecutive_losses": loss_streak.consecutive_losses, "loss_streak_triggered": loss_streak.triggered,
        },
        risk_flags=tuple(risk_flags),
        rationale=f"belt={belt} allow_new_trades={policy.allow_new_trades} loss_streak={loss_streak.consecutive_losses}",
    )
