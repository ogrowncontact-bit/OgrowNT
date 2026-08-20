"""Technical Analysis Agent — "PROMPT 9" §16-17.

Reads the same `IndicatorSet` every strategy already reads
(`packages/quant/indicators/core.py`), and forms a directional view purely
from indicator confirmation count (SMA cross, RSI zone, trend strength
sign) — deliberately simpler than any one Strategy's entry logic, since
this agent's job is to be an independent cross-check, not a fourth
strategy competing for the same signal.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentStatus, signal_from_direction_strength

AGENT_CODE = "technical_analysis"


def analyze(ctx: AgentContext) -> AgentMessage:
    ind = ctx.market.indicators
    if ind.sma_fast is None or ind.sma_slow is None or ind.rsi_14 is None or ind.trend_strength is None:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.UNAVAILABLE, signal=signal_from_direction_strength(None, 0.0),
            confidence=0.0, evidence={"reason": "insufficient_indicator_data"}, rationale="insufficient_indicator_data",
        )

    bullish = sum([ind.sma_fast > ind.sma_slow, ind.rsi_14 >= 55.0, ind.trend_strength > 0])
    bearish = sum([ind.sma_fast < ind.sma_slow, ind.rsi_14 <= 45.0, ind.trend_strength < 0])

    direction = None if bullish == bearish else ("long" if bullish > bearish else "short")
    strength = round(abs(bullish - bearish) / 3.0, 4)
    signal = signal_from_direction_strength(direction, strength)
    evidence = {
        "sma_fast": ind.sma_fast, "sma_slow": ind.sma_slow, "rsi_14": ind.rsi_14,
        "trend_strength": ind.trend_strength, "bullish_votes": bullish, "bearish_votes": bearish,
    }
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=signal, confidence=strength if direction else 0.0,
        evidence=evidence, rationale=f"{bullish} bullish vs {bearish} bearish indicator votes",
    )
