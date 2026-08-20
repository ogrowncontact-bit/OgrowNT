"""Contradiction Engine — "PROMPT 9" §43: detects pairwise disagreement
between directional agents and scores how severe the worst live conflict
is this cycle (0-100). A contradiction is two directional agents leaning
opposite ways (one long-leaning, one short-leaning), both reporting real
confidence in their read -- an agent that's simply NEUTRAL/NO_READ isn't
in conflict with anyone, it just has nothing to say.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.agents.specialists import SPECIALIST_REGISTRY

_LEAN: dict[AgentSignal, int] = {
    AgentSignal.STRONG_LONG: 2, AgentSignal.LONG: 1, AgentSignal.NEUTRAL: 0,
    AgentSignal.SHORT: -1, AgentSignal.STRONG_SHORT: -2, AgentSignal.NO_READ: 0,
}


@dataclass(frozen=True)
class ContradictionRecord:
    agent_code_a: str
    agent_code_b: str
    signal_a: AgentSignal
    signal_b: AgentSignal
    severity: float  # 0-100
    description: str


def find_contradictions(messages: dict[str, AgentMessage]) -> list[ContradictionRecord]:
    directional_codes = [code for code, meta in SPECIALIST_REGISTRY.items() if meta.directional]
    records: list[ContradictionRecord] = []

    for i, code_a in enumerate(directional_codes):
        message_a = messages.get(code_a)
        if message_a is None or message_a.status != AgentStatus.OK:
            continue
        lean_a = _LEAN[message_a.signal]
        if lean_a == 0:
            continue

        for code_b in directional_codes[i + 1:]:
            message_b = messages.get(code_b)
            if message_b is None or message_b.status != AgentStatus.OK:
                continue
            lean_b = _LEAN[message_b.signal]
            if lean_b == 0 or (lean_a > 0) == (lean_b > 0):
                continue  # no opinion, or same direction -- not a contradiction

            severity = round(min(100.0, (message_a.confidence + message_b.confidence) / 2 * 100), 2)
            records.append(
                ContradictionRecord(
                    agent_code_a=code_a, agent_code_b=code_b, signal_a=message_a.signal, signal_b=message_b.signal,
                    severity=severity,
                    description=f"{code_a} reads {message_a.signal.value} while {code_b} reads {message_b.signal.value}",
                )
            )
    return records


def contradiction_score(records: list[ContradictionRecord]) -> float:
    """The worst live disagreement this cycle -- a single strong two-agent
    conflict is exactly as concerning whether or not other agents happen to
    agree with each other, so this is a max, not an average."""
    if not records:
        return 0.0
    return max(r.severity for r in records)
