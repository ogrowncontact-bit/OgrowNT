"""Chief Decision Engine — "PROMPT 9" §40-46.

A pure function from this cycle's 18 `AgentMessage`s to one `Decision` —
never touches the DB, never executes anything, exactly like
`packages/risk/engine.py::evaluate_signal` is a pure function of its own
inputs. Persistence is `packages/agents/orchestrator.py`'s job.

DECISION_STATES mirror Prompt 9 §40 exactly (lower_snake_case internally,
matching this codebase's established "snake_case not UPPER_CASE" divergence
from Prompt 8 — see docs/autonomous-trading.md). BLOCKED is reserved for
two specific, structural reasons: a CRITICAL_AGENT_CODES agent is
unavailable this cycle (Prompt 9 §65: "Se agente crítico falhar: NO NEW
TRADES"), or the Emergency Guardian reports an active emergency. Everything
else that makes the picture too uncertain to act on (agents strongly
contradicting each other) is NO_TRADE, not BLOCKED — a distinct,
non-emergency "chose not to trade" state, matching Prompt 8's own
NO_TRADE precedent (a per-decision fact, not a system failure).

This engine is an ADDITIONAL pre-filter, wired into the worker cycle ahead
of (not instead of) the sovereign Risk Engine (Prompt 9 §14, §68's
"defense in depth" — Prompt 8 §75). A favorable Decision here never
bypasses `packages/risk/engine.py::evaluate_signal`; it only ever adds one
more thing that can say no.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.agents.consensus import ConsensusResult, compute_consensus
from packages.agents.contradiction import ContradictionRecord, contradiction_score, find_contradictions
from packages.agents.protocol import CRITICAL_AGENT_CODES, AgentMessage, AgentStatus

STRONG_LONG_BIAS = "strong_long_bias"
LONG_BIAS = "long_bias"
NEUTRAL = "neutral"
SHORT_BIAS = "short_bias"
STRONG_SHORT_BIAS = "strong_short_bias"
NO_TRADE = "no_trade"
BLOCKED = "blocked"

DECISION_STATES = (STRONG_LONG_BIAS, LONG_BIAS, NEUTRAL, SHORT_BIAS, STRONG_SHORT_BIAS, NO_TRADE, BLOCKED)

CONSENSUS_STRONG_THRESHOLD = 60.0
CONSENSUS_LEAN_THRESHOLD = 20.0
CONTRADICTION_NO_TRADE_THRESHOLD = 70.0
# A single agent's opinion alone never earns a *_BIAS state -- §41's
# "consenso", not one voice. Two independent votes minimum.
MIN_VOTING_AGENTS_FOR_BIAS = 2


@dataclass(frozen=True)
class Decision:
    decision_state: str
    consensus: ConsensusResult
    contradiction_score: float
    contradictions: list[ContradictionRecord]
    reasoning_summary: str
    agent_messages: dict[str, AgentMessage]
    blocked_reason: str | None = None
    critical_agent_failure: bool = False


def _critical_failure(messages: dict[str, AgentMessage]) -> str | None:
    for code in CRITICAL_AGENT_CODES:
        message = messages.get(code)
        if message is None or message.status != AgentStatus.OK:
            return code
    return None


def _emergency_flag(messages: dict[str, AgentMessage]) -> str | None:
    guardian = messages.get("emergency_guardian")
    if guardian is not None and "emergency" in guardian.risk_flags:
        return "emergency_guardian_flagged_emergency"
    return None


def _state_from_consensus(score: float, meaningful_votes: int) -> str:
    if meaningful_votes < MIN_VOTING_AGENTS_FOR_BIAS:
        return NEUTRAL
    if score >= CONSENSUS_STRONG_THRESHOLD:
        return STRONG_LONG_BIAS
    if score >= CONSENSUS_LEAN_THRESHOLD:
        return LONG_BIAS
    if score <= -CONSENSUS_STRONG_THRESHOLD:
        return STRONG_SHORT_BIAS
    if score <= -CONSENSUS_LEAN_THRESHOLD:
        return SHORT_BIAS
    return NEUTRAL


def decide(messages: dict[str, AgentMessage], reliability_scores: dict[str, float | None]) -> Decision:
    consensus = compute_consensus(messages, reliability_scores)
    contradictions = find_contradictions(messages)
    c_score = contradiction_score(contradictions)

    failed_critical = _critical_failure(messages)
    if failed_critical is not None:
        return Decision(
            decision_state=BLOCKED, consensus=consensus, contradiction_score=c_score, contradictions=contradictions,
            reasoning_summary=(
                f"BLOCKED: critical agent '{failed_critical}' is unavailable this cycle -- "
                "refusing to trade on an incomplete risk picture."
            ),
            agent_messages=messages, blocked_reason=f"critical_agent_unavailable:{failed_critical}", critical_agent_failure=True,
        )

    emergency_reason = _emergency_flag(messages)
    if emergency_reason is not None:
        return Decision(
            decision_state=BLOCKED, consensus=consensus, contradiction_score=c_score, contradictions=contradictions,
            reasoning_summary="BLOCKED: Emergency Guardian reports an active emergency condition (kill switch, pause, or safety belt EMERGENCY).",
            agent_messages=messages, blocked_reason=emergency_reason, critical_agent_failure=False,
        )

    if c_score >= CONTRADICTION_NO_TRADE_THRESHOLD:
        worst = max(contradictions, key=lambda r: r.severity)
        return Decision(
            decision_state=NO_TRADE, consensus=consensus, contradiction_score=c_score, contradictions=contradictions,
            reasoning_summary=f"NO_TRADE: agents disagree too strongly to act ({worst.description}, severity={worst.severity}).",
            agent_messages=messages,
        )

    state = _state_from_consensus(consensus.consensus_score, consensus.meaningful_votes)
    reasoning = (
        f"{state.upper()}: consensus_score={consensus.consensus_score} from {consensus.voting_agents}/"
        f"{consensus.eligible_agents} voting agents, contradiction_score={c_score}."
    )
    return Decision(
        decision_state=state, consensus=consensus, contradiction_score=c_score, contradictions=contradictions,
        reasoning_summary=reasoning, agent_messages=messages,
    )
