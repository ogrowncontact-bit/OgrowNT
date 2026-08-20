"""Anomaly Detection Agent — "PROMPT 9" §29.

Wraps the z-score outlier detector already in
`packages/quant/patterns/detector.py::detect_anomaly` rather than inventing
new statistics — confirmed present while mapping this prompt's 18 agents
against Phase 2-8's existing deterministic modules. Never directional: an
anomaly is a "something unusual just happened" flag for the Contradiction/
Chief Decision layer, not a trade idea of its own.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.quant.patterns.detector import detect_anomaly

AGENT_CODE = "anomaly_detection"


def analyze(ctx: AgentContext) -> AgentMessage:
    detection = detect_anomaly(ctx.market.candles, ctx.market.indicators)
    if detection is None:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0,
            evidence={"anomaly": False}, rationale="no statistical anomaly this cycle",
        )

    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL,
        confidence=round(detection.confidence, 4),
        evidence={"pattern_type": detection.pattern_type, "direction": detection.direction, "strength": detection.strength, "metadata": detection.metadata},
        risk_flags=("anomaly_detected",),
        rationale=f"statistical anomaly detected: {detection.metadata}",
    )
