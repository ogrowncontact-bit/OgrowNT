"""Data Quality Agent — "PROMPT 9" §27. Wraps
`packages/data/quality.py::compute_quality_score` — the existing per-asset
quality score (freshness/completeness/consistency/source availability/
timestamp accuracy) — as an agent, rather than recomputing anything. This
is one of the CRITICAL_AGENT_CODES (`packages/agents/protocol.py`): if it
cannot compute a score at all (no quality report available), the Chief
Decision Engine treats the whole cycle as untrustworthy, same principle as
the Risk Engine's own stale-data gate.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.data.quality import GOOD_THRESHOLD

AGENT_CODE = "data_quality"


def analyze(ctx: AgentContext) -> AgentMessage:
    report = ctx.quality_report
    if report is None:
        return AgentMessage(
            agent_code=AGENT_CODE, status=AgentStatus.UNAVAILABLE, signal=AgentSignal.NO_READ, confidence=0.0,
            evidence={"reason": "no_quality_report_available"}, rationale="no_quality_report_available",
        )

    risk_flags = () if report.status == "GOOD" and report.quality_score >= GOOD_THRESHOLD else ("data_quality_degraded",)
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL,
        confidence=round(report.quality_score / 100.0, 4),
        evidence={"quality_score": report.quality_score, "status": report.status, "components": report.components},
        risk_flags=risk_flags, rationale=f"data quality {report.quality_score}/100 ({report.status})",
    )
