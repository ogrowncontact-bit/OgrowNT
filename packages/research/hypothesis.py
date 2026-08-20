"""ResearchHypothesis engine — "PROMPT 10" §3-4, §11-15, §41.

`AutonomousResearchAgent`'s hypothesis-formulation half. Every hypothesis
starts from a DET-only template built from real, already-computed evidence
(`_det_narrative`) — an LLM (`packages/llm/hypothesis.py`) is an OPTIONAL
enrichment of the narrative fields on top of that, never a replacement:
hypothesis generation must keep working with no `ANTHROPIC_API_KEY`
configured, same "no hallucinated data" discipline as every other LLM call
in this codebase.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.llm.client import LLMClient
from packages.llm.hypothesis import propose_hypothesis
from packages.shared.models import ResearchHypothesis

TRIGGER_STRATEGY_DEGRADATION = "strategy_degradation"
TRIGGER_REGIME_CHANGE = "regime_change"
TRIGGER_AGENT_DISAGREEMENT = "agent_disagreement"
TRIGGER_ANOMALY = "anomaly"
TRIGGER_EXECUTION_DEGRADATION = "execution_degradation"
TRIGGER_DRIFT = "drift"
TRIGGER_MANUAL = "manual"
TRIGGERS = (
    TRIGGER_STRATEGY_DEGRADATION, TRIGGER_REGIME_CHANGE, TRIGGER_AGENT_DISAGREEMENT, TRIGGER_ANOMALY,
    TRIGGER_EXECUTION_DEGRADATION, TRIGGER_DRIFT, TRIGGER_MANUAL,
)

# §41: how recently an equivalent hypothesis (same trigger source + the
# same deterministic `problem` identifier) must have been proposed to skip
# re-proposing it rather than flooding the queue with duplicates.
SIMILARITY_COOLDOWN_DAYS = 14

RISK_LEVELS = ("low", "medium", "high")
COMPLEXITY_LEVELS = ("low", "medium", "high")


def _det_narrative(trigger: str, problem: str, evidence: dict) -> dict:
    """Always-available fallback -- guarantees a hypothesis is genuinely
    grounded in the real evidence handed to it even with no LLM configured."""
    evidence_lines = "; ".join(f"{k}={v}" for k, v in evidence.items())
    return {
        "title": f"{trigger.replace('_', ' ').title()}: {problem}"[:80],
        "description": f"Trigger '{trigger}' detected for {problem}. Evidence: {evidence_lines}.",
        "hypothesis": f"A targeted experiment on {problem} may identify a testable, addressable cause behind this trigger.",
        "expected_effect": (
            "A validated control-vs-candidate experiment would show whether a specific change measurably "
            "improves the outcome, without a fabricated claim of what that change is ahead of time."
        ),
    }


def find_similar_recent_hypothesis(
    db: Session, *, source: str, problem: str, cooldown_days: int = SIMILARITY_COOLDOWN_DAYS
) -> ResearchHypothesis | None:
    """§41's ResearchSimilarityEngine: a structured-field check (same
    trigger source AND the same deterministic `problem` identifier, e.g.
    "strategy:momentum_v1", within the cooldown window) — real semantic
    similarity would need an embedding model this environment doesn't have
    configured, the same honest limitation
    `packages/quant/learning/memory.py` already documents for Market
    Memory's own similarity search.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
    return (
        db.execute(
            select(ResearchHypothesis)
            .where(ResearchHypothesis.source == source, ResearchHypothesis.problem == problem, ResearchHypothesis.created_at >= cutoff)
            .order_by(ResearchHypothesis.created_at.desc())
        )
        .scalars()
        .first()
    )


@dataclass(frozen=True)
class HypothesisQuality:
    testability: bool
    data_availability: bool
    has_expected_mechanism: bool
    novelty: bool
    complexity: str


def assess_quality(*, hypothesis_text: str, expected_effect: str, assets: list, is_novel: bool, complexity: str) -> HypothesisQuality:
    return HypothesisQuality(
        testability=bool(expected_effect and len(expected_effect) > 10),
        data_availability=bool(assets),
        has_expected_mechanism=bool(hypothesis_text and len(hypothesis_text) > 20),
        novelty=is_novel,
        complexity=complexity,
    )


def compute_priority_score(*, quality: HypothesisQuality, evidence_strength: float, risk: str, complexity: str) -> float:
    """0-100, "PROMPT 10" §15: potential impact (evidence_strength, 0-1),
    evidence quality dimensions, cost/complexity, and risk. A near-
    duplicate of a recent hypothesis is heavily penalized rather than
    silently filtered -- callers still get a score to compare against, but
    create_hypothesis() below never persists a non-novel one anyway."""
    score = 50.0 + max(0.0, min(1.0, evidence_strength)) * 30.0
    score += 10.0 if quality.testability else -10.0
    score += 5.0 if quality.data_availability else -5.0
    score += 5.0 if quality.has_expected_mechanism else -5.0
    score -= 0.0 if quality.novelty else 25.0
    score += {"low": 0.0, "medium": -5.0, "high": -15.0}.get(risk, -5.0)
    score += {"low": 0.0, "medium": -5.0, "high": -10.0}.get(complexity, -5.0)
    return round(max(0.0, min(100.0, score)), 2)


def create_hypothesis(
    db: Session, *, trigger: str, problem: str, observation: str, evidence: dict,
    assets: list[str] | None = None, timeframes: list[str] | None = None, regimes: list[str] | None = None,
    risk: str = "medium", complexity: str = "medium", evidence_strength: float = 0.5,
    llm_client: LLMClient | None = None,
) -> ResearchHypothesis | None:
    """Returns None (writes nothing) when an equivalent hypothesis was
    already proposed recently — §41's "don't repeat failed/existing
    research", enforced structurally rather than left to caller discipline.
    """
    if trigger not in TRIGGERS:
        raise ValueError(f"unknown research trigger: {trigger!r}")
    if risk not in RISK_LEVELS or complexity not in COMPLEXITY_LEVELS:
        raise ValueError("risk/complexity must be one of low/medium/high")

    existing = find_similar_recent_hypothesis(db, source=trigger, problem=problem)
    if existing is not None:
        return None

    narrative = _det_narrative(trigger, problem, evidence)
    if llm_client is not None:
        enriched = propose_hypothesis(llm_client, trigger=trigger, evidence=evidence)
        if enriched is not None:
            narrative = {
                "title": enriched.title, "description": enriched.description,
                "hypothesis": enriched.hypothesis, "expected_effect": enriched.expected_effect,
            }

    assets, timeframes, regimes = list(assets or []), list(timeframes or []), list(regimes or [])
    quality = assess_quality(
        hypothesis_text=narrative["hypothesis"], expected_effect=narrative["expected_effect"],
        assets=assets, is_novel=True, complexity=complexity,
    )
    priority_score = compute_priority_score(quality=quality, evidence_strength=evidence_strength, risk=risk, complexity=complexity)

    row = ResearchHypothesis(
        title=narrative["title"], description=narrative["description"], problem=problem, observation=observation,
        hypothesis=narrative["hypothesis"], expected_effect=narrative["expected_effect"], risk=risk,
        assets=assets, timeframes=timeframes, regimes=regimes, source=trigger,
        quality={
            "testability": quality.testability, "data_availability": quality.data_availability,
            "has_expected_mechanism": quality.has_expected_mechanism, "novelty": quality.novelty, "complexity": quality.complexity,
        },
        priority_score=priority_score, status="proposed",
    )
    db.add(row)
    db.commit()
    return row
