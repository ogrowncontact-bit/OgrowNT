"""Chief Quant Agent — "PROMPT 9" §15.

Distinct from the `ChiefDecisionEngine` (`packages/agents/chief.py`), which
aggregates ALL 18 agents' messages: this is one specialist among the 18,
giving a portfolio-level "which way do the numbers point" read by
regime-weighting every registered strategy's own
`calculate_expected_value()` (`packages/quant/strategies/base.py` — already
exists precisely so strategies can rank their own candidates) rather than
re-deriving a new expected-value formula. A senior-strategist-style
synthesis, built entirely from already-computed, already-trusted numbers.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentStatus, signal_from_direction_strength
from packages.quant.strategies import ALL_STRATEGIES

AGENT_CODE = "chief_quant"


def analyze(ctx: AgentContext) -> AgentMessage:
    votes = []
    for strategy in ALL_STRATEGIES:
        analysis = strategy.analyze(ctx.market)
        if analysis.direction is None:
            continue
        ev = strategy.calculate_expected_value(ctx.market, analysis)
        sign = 1 if analysis.direction == "long" else -1
        votes.append((strategy.code, sign * ev))

    if not votes:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=signal_from_direction_strength(None, 0.0),
            confidence=0.0, evidence={"strategy_votes": 0}, rationale="no strategy has a directional read this cycle",
        )

    net = sum(v for _, v in votes) / len(votes)  # -1..1, regime-fit-weighted
    direction = None if abs(net) < 0.1 else ("long" if net > 0 else "short")
    strength = round(min(1.0, abs(net)), 4)
    signal = signal_from_direction_strength(direction, strength)
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=signal, confidence=strength if direction else 0.0,
        evidence={"strategy_votes": dict(votes), "net_expected_value": round(net, 4), "regime": ctx.market.regime.regime},
        rationale=f"regime-weighted expected value across {len(votes)} strategies = {round(net, 4)}",
    )
