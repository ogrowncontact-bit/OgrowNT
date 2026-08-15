"""Research Agent — docs/blueprint/04-agents-architecture.md#agent-14,
docs/blueprint/11-prompts/research-agent.md.

Two independent DET-bracketed steps around one LLM call:
1. DET candidate selection: only patterns/strategies with enough sample and
   a genuinely poor recent expectancy are worth an LLM call at all.
2. LLM hypothesis (packages/llm/research.py): written as
   `learned_rules.status='candidate'`, never higher.
3. DET validation: a fresh, independent read of the raw per-trade R-multiple
   sample for that scope, checked with a one-sample z-test against
   H0: mean R-multiple >= 0. This is deliberately simple (a normal
   approximation, one-tailed, no multiple-comparison correction) rather
   than a full backtest-grade statistical pipeline — that level of rigor is
   Phase 6 (docs/blueprint/10-backtesting-paper-trading.md); what matters
   here is that validation never depends on the LLM's stated confidence,
   only on data queried fresh from the database.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.llm.client import LLMClient
from packages.llm.research import propose_rule
from packages.shared.models import (
    LearnedRule,
    MarketRegime,
    Pattern,
    PatternPerformance,
    Position,
    Signal,
    StrategyPerformance,
    StrategyRow,
    Trade,
)

logger = logging.getLogger("learning.research")

# An LLM call is only worth making once the underlying sample already looks
# poor — avoids spending calls (and noise) on patterns/strategies that are
# simply new or currently healthy.
MIN_SAMPLE_FOR_CANDIDATE = 8
CANDIDATE_EXPECTANCY_THRESHOLD = -0.1  # R-multiple

# DET validation thresholds — see module docstring for why this is a
# deliberately simple z-test, not a formal backtest validation.
MIN_SAMPLE_FOR_VALIDATION = 20
Z_CRITICAL = -1.645  # one-tailed, ~95% confidence under a normal approximation


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pattern_candidates(db: Session) -> list[PatternPerformance]:
    return (
        db.query(PatternPerformance)
        .filter(PatternPerformance.sample_size >= MIN_SAMPLE_FOR_CANDIDATE)
        .filter(PatternPerformance.expectancy.isnot(None))
        .filter(PatternPerformance.expectancy <= CANDIDATE_EXPECTANCY_THRESHOLD)
        .all()
    )


def _strategy_candidates(db: Session) -> list[StrategyPerformance]:
    latest_by_strategy: dict[int, StrategyPerformance] = {}
    for perf in db.query(StrategyPerformance).order_by(StrategyPerformance.as_of.asc()).all():
        latest_by_strategy[perf.strategy_id] = perf
    return [
        perf for perf in latest_by_strategy.values()
        if perf.window_trades >= MIN_SAMPLE_FOR_CANDIDATE
        and perf.expectancy is not None
        and perf.expectancy <= CANDIDATE_EXPECTANCY_THRESHOLD
    ]


def _existing_candidate_scopes(db: Session) -> set[str]:
    return {row[0] for row in db.query(LearnedRule.scope).filter(LearnedRule.status == "candidate").all()}


def run_research_cycle(db: Session, llm_client: LLMClient) -> dict:
    scopes_seen = _existing_candidate_scopes(db)
    proposed = 0

    for perf in _pattern_candidates(db):
        scope = f"pattern:{perf.pattern_type}:{perf.regime}"
        if scope in scopes_seen:
            continue
        rule = propose_rule(
            llm_client, scope=scope,
            stats={"sample_size": perf.sample_size, "win_rate": perf.win_rate, "expectancy": perf.expectancy, "regime": perf.regime},
        )
        if rule is None:
            continue
        db.add(
            LearnedRule(
                scope=scope, condition=rule.condition, conclusion=rule.conclusion,
                confidence=rule.confidence, sample_size=perf.sample_size, status="candidate",
            )
        )
        scopes_seen.add(scope)
        proposed += 1

    for perf in _strategy_candidates(db):
        strategy = db.get(StrategyRow, perf.strategy_id)
        if strategy is None:
            continue
        scope = f"strategy:{strategy.code}"
        if scope in scopes_seen:
            continue
        rule = propose_rule(
            llm_client, scope=scope,
            stats={
                "sample_size": perf.window_trades, "win_rate": perf.win_rate,
                "expectancy": perf.expectancy, "worst_regime": perf.worst_regime,
            },
        )
        if rule is None:
            continue
        db.add(
            LearnedRule(
                scope=scope, condition=rule.condition, conclusion=rule.conclusion,
                confidence=rule.confidence, sample_size=perf.window_trades, status="candidate",
            )
        )
        scopes_seen.add(scope)
        proposed += 1

    db.commit()
    validated, rejected = _validate_candidates(db)
    return {"proposed": proposed, "validated": validated, "rejected": rejected}


def _r_multiples_for_strategy(db: Session, code: str) -> list[float]:
    strategy = db.query(StrategyRow).filter(StrategyRow.code == code).first()
    if strategy is None:
        return []
    rows = (
        db.query(Trade.r_multiple)
        .join(Position, Trade.position_id == Position.id)
        .filter(Position.strategy_id == strategy.id, Trade.r_multiple.isnot(None))
        .all()
    )
    return [row[0] for row in rows]


def _r_multiples_for_pattern(db: Session, pattern_type: str, regime: str) -> list[float]:
    rows = (
        db.query(Trade.r_multiple)
        .join(Position, Trade.position_id == Position.id)
        .join(Signal, Position.signal_id == Signal.id)
        .join(Pattern, Signal.pattern_id == Pattern.id)
        .join(MarketRegime, Signal.regime_id == MarketRegime.id)
        .filter(Pattern.pattern_type == pattern_type, MarketRegime.regime == regime, Trade.r_multiple.isnot(None))
        .all()
    )
    return [row[0] for row in rows]


def _z_statistic(r_multiples: list[float]) -> float | None:
    """One-sample z-statistic for H0: mean == 0. None only when undefined
    (fewer than 2 points). Zero variance (every trade in the sample landed
    on exactly the same R-multiple) isn't a division-by-zero to discard —
    it's the most extreme case the sample can show, so it maps to the most
    extreme z rather than "no signal"."""
    n = len(r_multiples)
    if n < 2:
        return None
    mean = sum(r_multiples) / n
    variance = sum((r - mean) ** 2 for r in r_multiples) / (n - 1)
    std = math.sqrt(variance)
    if std == 0:
        return float("-inf") if mean < 0 else float("inf")
    standard_error = std / math.sqrt(n)
    return mean / standard_error


def _validate_candidates(db: Session) -> tuple[int, int]:
    validated, rejected = 0, 0
    for rule in db.query(LearnedRule).filter(LearnedRule.status == "candidate").all():
        kind, _, rest = rule.scope.partition(":")
        if kind == "strategy":
            r_multiples = _r_multiples_for_strategy(db, rest)
        elif kind == "pattern":
            pattern_type, _, regime = rest.partition(":")
            r_multiples = _r_multiples_for_pattern(db, pattern_type, regime)
        else:
            logger.warning("Unrecognized learned_rule scope kind, skipping: %r", rule.scope)
            continue

        if len(r_multiples) < MIN_SAMPLE_FOR_VALIDATION:
            continue  # not enough data yet either way — stays 'candidate'

        z = _z_statistic(r_multiples)
        rule.sample_size = len(r_multiples)
        rule.validated_at = _utcnow()
        if z is not None and z <= Z_CRITICAL:
            rule.status = "validated"
            validated += 1
        else:
            rule.status = "rejected"
            rejected += 1
        db.add(rule)

    db.commit()
    return validated, rejected
