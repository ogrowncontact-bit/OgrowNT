"""Strategy Health Agent — "PROMPT 9" §28. Wraps the existing
`packages/risk/strategy_health.py::classify_strategy_health` verdict for
the strategy this cycle is evaluating, over the same `health_score`
(`packages/quant/learning/strategy_stats.py`) the Risk Engine's own step 10
consults — one source of truth, read by both.
"""
from __future__ import annotations

from sqlalchemy import select

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.risk.strategy_health import classify_strategy_health
from packages.shared.models import StrategyPerformance

AGENT_CODE = "strategy_health"


def _latest_health_score(ctx: AgentContext) -> float | None:
    if ctx.strategy_row is None:
        return None
    row = ctx.db.execute(
        select(StrategyPerformance)
        .where(StrategyPerformance.strategy_id == ctx.strategy_row.id)
        .order_by(StrategyPerformance.as_of.desc())
        .limit(1)
    ).scalar_one_or_none()
    return row.health_score if row is not None else None


def analyze(ctx: AgentContext) -> AgentMessage:
    if ctx.strategy_row is None:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.UNAVAILABLE, signal=AgentSignal.NO_READ, confidence=0.0,
            evidence={"reason": "no_strategy_in_context"}, rationale="no_strategy_in_context",
        )

    health_score = _latest_health_score(ctx)
    verdict = classify_strategy_health(health_score)
    risk_flags = ("strategy_quarantined",) if verdict.blocked else (("strategy_degraded",) if verdict.status == "degraded" else ())
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL,
        confidence=0.0 if health_score is None else 1.0,
        evidence={"health_score": health_score, "status": verdict.status, "size_multiplier": verdict.size_multiplier},
        risk_flags=risk_flags, rationale=f"strategy health={verdict.status} score={health_score}",
    )
