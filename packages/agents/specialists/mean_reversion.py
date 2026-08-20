"""Mean Reversion Agent — "PROMPT 9" §23. Thin wrapper over
`packages/quant/strategies/mean_reversion.py::MeanReversionStrategy.analyze()`
— same rationale as the Momentum Agent's wrapper.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus, signal_from_direction_strength
from packages.quant.strategies.mean_reversion import MeanReversionStrategy

AGENT_CODE = "mean_reversion"
_strategy = MeanReversionStrategy()


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
        evidence=dict(result.rationale), rationale=f"mean_reversion direction={result.direction} strength={result.strength}",
    )
