"""Momentum Agent — "PROMPT 9" §22. Thin wrapper over the already-existing
`packages/quant/strategies/momentum.py::MomentumStrategy.analyze()` — the
Strategy Engine's own read, exposed as one more independent vote rather
than a second, competing implementation of the same math.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus, signal_from_direction_strength
from packages.quant.strategies.momentum import MomentumStrategy

AGENT_CODE = "momentum"
_strategy = MomentumStrategy()


def analyze(ctx: AgentContext) -> AgentMessage:
    result = _strategy.analyze(ctx.market)
    if result.rationale.get("reason") == "insufficient_data":
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.UNAVAILABLE, signal=AgentSignal.NO_READ, confidence=0.0,
            evidence={"reason": "insufficient_data"}, rationale="insufficient_data",
        )

    signal = signal_from_direction_strength(result.direction, result.strength)
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=signal,
        confidence=round(result.strength, 4) if result.direction else 0.0,
        evidence=dict(result.rationale), rationale=f"momentum direction={result.direction} strength={result.strength}",
    )
