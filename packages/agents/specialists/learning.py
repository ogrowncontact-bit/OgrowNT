"""Learning Agent — "PROMPT 9" §35. Synthesizes the same rolling
`StrategyPerformance`/health-score history the Strategy Health Agent and
Risk Engine already read (`packages/quant/learning/strategy_stats.py`)
into a single "is the system's own recent track record trustworthy right
now" read — deliberately not a duplicate of the Strategy Health Agent
(which is per-strategy, size-multiplier-shaped); this one is a broader
"how has learning/adaptation been going" context signal, non-directional.
"""
from __future__ import annotations

from sqlalchemy import select

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.quant.learning.quarantine import HEALTH_SCORE_QUARANTINE_THRESHOLD
from packages.shared.models import StrategyPerformance

AGENT_CODE = "learning"


def analyze(ctx: AgentContext) -> AgentMessage:
    latest_by_strategy: dict[int, StrategyPerformance] = {}
    for perf in ctx.db.execute(select(StrategyPerformance).order_by(StrategyPerformance.as_of.asc())).scalars().all():
        latest_by_strategy[perf.strategy_id] = perf

    scored = [p for p in latest_by_strategy.values() if p.health_score is not None]
    if not scored:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0,
            evidence={"reason": "no strategy has enough closed trades yet to score"}, rationale="insufficient trade history for any strategy",
        )

    quarantined = [p for p in scored if p.health_score is not None and p.health_score < HEALTH_SCORE_QUARANTINE_THRESHOLD]
    avg_health = round(sum(p.health_score for p in scored if p.health_score is not None) / len(scored), 2)
    risk_flags = ("multiple_strategies_quarantined",) if len(quarantined) > 1 else ()

    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=round(min(1.0, len(scored) / 5.0), 4),
        evidence={"strategies_scored": len(scored), "avg_health_score": avg_health, "quarantined_count": len(quarantined)},
        risk_flags=risk_flags,
        rationale=f"avg strategy health={avg_health} across {len(scored)} scored strategies, {len(quarantined)} quarantined",
    )
