"""Pattern Hunter Agent — "PROMPT 9" §18-19.

Wraps `packages/quant/patterns/detector.py::detect_all` — the same
deterministic pattern detectors the strategy cycle already runs — and
reports the strongest non-anomaly, non-cross-asset detection as evidence.
`anomaly` and `cross_asset` detections are deliberately excluded here: they
have their own dedicated agents (Anomaly Detection §21, and cross-asset
needs externally supplied peer returns this agent's context does not
guarantee) so the same detection isn't double-counted under two agent
codes in the Consensus Engine.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus, signal_from_direction_strength
from packages.quant.patterns.detector import detect_all

AGENT_CODE = "pattern_hunter"
_EXCLUDED_TYPES = {"anomaly", "cross_asset"}
_DIRECTION_MAP = {"bullish": "long", "bearish": "short"}


def analyze(ctx: AgentContext) -> AgentMessage:
    detections = [d for d in detect_all(ctx.market.candles, ctx.market.indicators) if d.pattern_type not in _EXCLUDED_TYPES]
    if not detections:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0,
            evidence={"detections": 0}, rationale="no pattern detected this cycle",
        )

    best = max(detections, key=lambda d: d.strength * d.confidence)
    direction = _DIRECTION_MAP.get(best.direction)
    strength = round(best.strength * best.confidence, 4)
    signal = signal_from_direction_strength(direction, strength)
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=signal, confidence=strength if direction else 0.0,
        evidence={
            "pattern_type": best.pattern_type, "pattern_class": best.pattern_class, "direction": best.direction,
            "strength": best.strength, "confidence": best.confidence, "candidate_count": len(detections),
        },
        rationale=f"strongest pattern: {best.pattern_type} ({best.pattern_class}, {best.direction})",
    )
