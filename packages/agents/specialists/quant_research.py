"""Quant Research Agent — "PROMPT 9" §31.

Wraps the existing `LearnedRule` memory (`packages/quant/learning/
research.py`) — validated rules for this strategy's scope
(`f"strategy:{code}"`, exactly what `run_research_cycle` writes). Honest
divergence from a literal reading of the spec: a validated `LearnedRule`'s
`condition`/`conclusion` are free-form LLM-authored JSON/text with no fixed
schema carrying a machine-readable trade direction (see
`packages/llm/research.py::RuleProposal`) — parsing a direction out of
prose here would mean either a second LLM call this cycle (latency/cost
inside a real-time worker loop) or a fragile heuristic parser, both against
this codebase's "no hallucinated data" discipline. So this agent reports
WHAT the system has learned (validated rule count + confidence) as
evidence for the dashboard/Chief Decision trace, and never casts a
directional vote — same non-directional shape as the Sentiment Agent.
"""
from __future__ import annotations

from sqlalchemy import select

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.shared.models import LearnedRule

AGENT_CODE = "quant_research"


def analyze(ctx: AgentContext) -> AgentMessage:
    if ctx.strategy_row is None:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0,
            evidence={"validated_rules": 0}, rationale="no strategy in context",
        )

    scope = f"strategy:{ctx.strategy_row.code}"
    rules = ctx.db.execute(
        select(LearnedRule).where(LearnedRule.scope == scope, LearnedRule.status == "validated")
    ).scalars().all()
    if not rules:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=0.0,
            evidence={"scope": scope, "validated_rules": 0}, rationale="no validated learned rules for this scope",
        )

    avg_confidence = round(sum(r.confidence for r in rules) / len(rules), 4)
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL, confidence=avg_confidence,
        evidence={
            "scope": scope, "validated_rules": len(rules),
            "conclusions": [r.conclusion for r in rules[:5]],
        },
        risk_flags=("learned_rule_available",),
        rationale=f"{len(rules)} validated learned rule(s) for {scope}, avg confidence {avg_confidence}",
    )
