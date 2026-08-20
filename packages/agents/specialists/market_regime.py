"""Market Regime Agent — "PROMPT 9" §20.

Reads `MarketContext.regime` (`packages/quant/regime/classifier.py`'s
already-computed `RegimeResult` for this cycle) rather than reclassifying —
there is exactly one regime read per (asset, cycle) in this system, and
every consumer (strategies, Risk Engine, this agent) shares it, never
recomputes its own.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus, signal_from_direction_strength

AGENT_CODE = "market_regime"
_DIRECTION_MAP = {"trending_bull": "long", "euphoria": "long", "trending_bear": "short", "panic": "short"}
_RISK_FLAG_REGIMES = {"high_volatility": "high_volatility_regime", "panic": "panic_regime", "transition": "regime_transition_unresolved"}


def analyze(ctx: AgentContext) -> AgentMessage:
    regime = ctx.market.regime
    if regime.regime == "unknown":
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.UNAVAILABLE, signal=AgentSignal.NO_READ, confidence=0.0,
            evidence={"reason": "insufficient_history_for_regime"}, rationale="insufficient_history_for_regime",
        )

    direction = _DIRECTION_MAP.get(regime.regime)
    signal = signal_from_direction_strength(direction, regime.confidence)
    risk_flags = tuple(flag for key, flag in _RISK_FLAG_REGIMES.items() if regime.regime == key)
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=signal, confidence=round(regime.confidence, 4),
        evidence={"regime": regime.regime, "features": regime.features}, risk_flags=risk_flags,
        rationale=f"regime={regime.regime} confidence={regime.confidence}",
    )
