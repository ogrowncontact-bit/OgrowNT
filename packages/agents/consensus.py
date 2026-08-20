"""Consensus Engine — "PROMPT 9" §41-42: "NÃO É VOTO MAJORITÁRIO. É
consenso ponderado por confiabilidade + evidência".

Aggregates every `directional=True` agent's message into one
`consensus_score` in [-100, 100] (-100 = maximum conviction short,
+100 = maximum conviction long), weighted by three independent factors per
agent, never a plain vote count:

- evidence: the agent's own reported `confidence` for this message
- reliability: `AgentReliability.reliability_score` (packages/agents/
  reliability.py), defaulting to a neutral 0.5 for an agent with no
  settled-prediction track record yet -- an untested agent gets counted,
  just not over-trusted
- recency: a message past its own `expires_at` counts for less, since it's
  stale evidence about a market that has since moved on
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.agents.protocol import AgentMessage, AgentSignal, AgentStatus
from packages.agents.specialists import SPECIALIST_REGISTRY

SIGNAL_VALUE: dict[AgentSignal, float] = {
    AgentSignal.STRONG_LONG: 100.0, AgentSignal.LONG: 50.0, AgentSignal.NEUTRAL: 0.0,
    AgentSignal.SHORT: -50.0, AgentSignal.STRONG_SHORT: -100.0, AgentSignal.NO_READ: 0.0,
}
NEUTRAL_RELIABILITY_PRIOR = 0.5  # no track record yet -- neither trusted nor discounted to zero
STALE_MESSAGE_WEIGHT = 0.3


@dataclass(frozen=True)
class ConsensusContribution:
    agent_code: str
    signal: AgentSignal
    confidence: float
    reliability_weight: float
    recency_weight: float
    weight: float
    value: float


@dataclass(frozen=True)
class ConsensusResult:
    consensus_score: float  # -100..100
    voting_agents: int  # responded OK with a real signal (NEUTRAL counts -- "no edge" is still an answer)
    # Responded with actual non-zero conviction (weight > 0) -- what
    # packages/agents/chief.py's MIN_VOTING_AGENTS_FOR_BIAS gate keys on,
    # since a room full of honest "no opinion" NEUTRALs must never let a
    # single agent's lone conviction alone swing the decision to a *_BIAS
    # state (Prompt 9 §41: "consenso", not one voice).
    meaningful_votes: int
    eligible_agents: int
    contributions: dict[str, ConsensusContribution] = field(default_factory=dict)


def compute_consensus(messages: dict[str, AgentMessage], reliability_scores: dict[str, float | None]) -> ConsensusResult:
    directional_codes = [code for code, meta in SPECIALIST_REGISTRY.items() if meta.directional]
    contributions: dict[str, ConsensusContribution] = {}
    weighted_sum, weight_total = 0.0, 0.0
    meaningful_votes = 0

    for code in directional_codes:
        message = messages.get(code)
        if message is None or message.status != AgentStatus.OK or message.signal == AgentSignal.NO_READ:
            continue

        reliability = reliability_scores.get(code)
        reliability_weight = (reliability / 100.0) if reliability is not None else NEUTRAL_RELIABILITY_PRIOR
        recency_weight = STALE_MESSAGE_WEIGHT if message.is_expired else 1.0
        weight = message.confidence * reliability_weight * recency_weight
        value = SIGNAL_VALUE[message.signal]

        contributions[code] = ConsensusContribution(
            agent_code=code, signal=message.signal, confidence=message.confidence,
            reliability_weight=round(reliability_weight, 4), recency_weight=recency_weight,
            weight=round(weight, 4), value=value,
        )
        weighted_sum += value * weight
        weight_total += weight
        if weight > 0:
            meaningful_votes += 1

    consensus_score = round(weighted_sum / weight_total, 2) if weight_total > 0 else 0.0
    return ConsensusResult(
        consensus_score=consensus_score, voting_agents=len(contributions), meaningful_votes=meaningful_votes,
        eligible_agents=len(directional_codes), contributions=contributions,
    )
