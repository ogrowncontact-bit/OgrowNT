"""Macro Agent — "PROMPT 9" §24. Reads the already-persisted `macro_events`
calendar (`apps/worker/macro_agent.py`'s own cadence maintains it from
`MacroCalendarProvider`, Prompt 6) — never re-fetched from the live
provider per asset per cycle, and never directional: a scheduled macro
release does not honestly imply which way price will move (the same "no
hallucinated data" discipline behind Prompt 6's Sentiment Engine not
converting tone into direction). This agent's only real output is a
timing risk flag when a high/critical-importance event sits inside the
lookahead window, letting the Contradiction/Chief Decision layer treat
"about to have a scheduled shock" as a real, evidenced risk without ever
guessing its direction.
"""
from __future__ import annotations

from packages.agents.context import AgentContext
from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus

AGENT_CODE = "macro"
IMMINENT_HOURS = 24.0
_FLAGGED_IMPORTANCE = {"high", "critical"}


def analyze(ctx: AgentContext) -> AgentMessage:
    imminent = [
        e for e in ctx.macro_events
        if e.importance in _FLAGGED_IMPORTANCE and 0 <= (e.scheduled_at - ctx.now).total_seconds() / 3600.0 <= IMMINENT_HOURS
    ]
    risk_flags = ("macro_event_imminent",) if imminent else ()
    return AgentMessage(
        agent_code=AGENT_CODE, status=AgentStatus.OK, signal=AgentSignal.NEUTRAL,
        confidence=1.0 if imminent else 0.0,
        evidence={"imminent_events": [{"event": e.event, "importance": e.importance, "scheduled_at": e.scheduled_at.isoformat()} for e in imminent], "total_events_in_window": len(ctx.macro_events)},
        risk_flags=risk_flags,
        rationale=f"{len(imminent)} high/critical macro event(s) within {IMMINENT_HOURS}h" if imminent else "no imminent high-importance macro events",
    )
