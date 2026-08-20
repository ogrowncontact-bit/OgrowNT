"""Multi-Agent protocol — "PROMPT 9" §1-10.

Every specialist agent is a pure function: `AgentContext` in, `AgentMessage`
out. No agent ever executes a trade, writes to `packages.execution`, or
mutates portfolio/risk state — see `packages/agents/permissions.py` for the
structurally-enforced boundary (`tests/test_agent_sandbox.py`). Agents only
ever ADD evidence to the Chief Decision Engine (`packages/agents/chief.py`);
the sovereign Risk Engine (`packages/risk/engine.py`) remains the only code
path that can approve a real order (see
`tests/test_critical_safety_battery.py`), completely unchanged by this
package.

"No hallucinated data" (Prompt 9 §44) applies here exactly like everywhere
else in this codebase: an agent that cannot form a view (missing data,
insufficient history, a dependency raised) reports `AgentStatus.UNAVAILABLE`
with `AgentSignal.NO_READ` and zero confidence — it never invents a
directional read to avoid looking idle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class AgentSignal(StrEnum):
    STRONG_LONG = "strong_long"
    LONG = "long"
    NEUTRAL = "neutral"
    SHORT = "short"
    STRONG_SHORT = "strong_short"
    NO_READ = "no_read"  # an honest "I have no opinion" -- NOT the same as NEUTRAL (a read of "range-bound/no edge")


class AgentStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"  # data/dependency missing this cycle -- never fabricate a signal to fill the gap
    QUARANTINED = "quarantined"  # the reliability engine has silenced this agent (packages/agents/reliability.py)


# Agents whose UNAVAILABLE status this cycle forces the Chief Decision Engine
# to BLOCKED regardless of what every other agent says — Prompt 9 §65:
# "Se agente crítico falhar: # NO NEW TRADES". Emergency Guardian and Risk
# Guardian both read directly from the same sovereign risk state
# (SystemState/PortfolioState) the real Risk Engine gates on; if the multi-
# agent layer can't even read that state, it must not pretend it's safe.
CRITICAL_AGENT_CODES = frozenset({"emergency_guardian", "risk_guardian", "data_quality"})


@dataclass(frozen=True)
class AgentMessage:
    agent_code: str
    status: AgentStatus
    signal: AgentSignal
    confidence: float  # 0.0-1.0; MUST be 0.0 whenever status != OK
    evidence: dict = field(default_factory=dict)
    risk_flags: tuple[str, ...] = ()
    rationale: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.status != AgentStatus.OK and self.confidence != 0.0:
            raise ValueError("non-OK agent messages must carry zero confidence -- no fabricated conviction")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be within [0.0, 1.0]")

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.now(timezone.utc) >= self.expires_at


def unavailable(agent_code: str, reason: str) -> AgentMessage:
    """The one honest way for a specialist to report "I couldn't form a
    view this cycle" -- used for missing data/insufficient history, never
    for "no strong opinion" (that's AgentSignal.NEUTRAL with status=OK)."""
    return AgentMessage(
        agent_code=agent_code, status=AgentStatus.UNAVAILABLE, signal=AgentSignal.NO_READ,
        confidence=0.0, evidence={"reason": reason}, rationale=reason,
    )


def signal_from_direction_strength(direction: str | None, strength: float) -> AgentSignal:
    """Shared mapping from a Strategy-style (direction, 0..1 strength) pair
    into the 5-way AgentSignal vocabulary -- >=0.7 strength is a STRONG_*
    read, otherwise a plain directional lean, matching the DECISION_STATES
    5-way split in packages/agents/chief.py."""
    if direction is None:
        return AgentSignal.NEUTRAL
    if direction == "long":
        return AgentSignal.STRONG_LONG if strength >= 0.7 else AgentSignal.LONG
    return AgentSignal.STRONG_SHORT if strength >= 0.7 else AgentSignal.SHORT
