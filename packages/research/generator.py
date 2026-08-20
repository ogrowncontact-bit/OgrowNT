"""Strategy Generator — mutation + bounded genetic search over parameters,
plus DSL feature-filter structural proposals — "PROMPT 10" §16-21.

Two independent mutation families, both reusing proven primitives instead
of inventing new backtesting math:

- **Parameter mutation / genetic search** perturbs a strategy's own numeric
  constructor parameters (`packages/backtest/optimize.py::numeric_params`'s
  exact definition of "numeric parameter") via random mutation and uniform
  crossover across a bounded number of generations. Fitness during the
  search is the SAME cheap walk-forward pooled-expectancy signal
  `optimize.py`'s one-shot grid search already uses — not the full
  8-engine `packages.research.experiment.evaluate_arm` pipeline, which
  would be too expensive to run `population_size x generations` times.
  The winner is a proposal only: a caller decides whether to spend a full
  `run_experiment` validating it before it becomes a `StrategyVersion`.

- **Feature-filter proposals** turn `packages.research.features`'s
  observed (pattern_type, regime) evidence into a candidate
  `packages.research.dsl` condition — "only take signals while the regime
  matches where this pattern shows a real, non-regime-dependent edge."

Nothing here writes to the database. `propose_candidates` returns plain
dataclasses; turning one into a persisted `StrategyVersion` row is
`packages.research.versioning.create_version`'s job — a deliberate
separation so search and persistence stay independently testable.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.backtest.optimize import numeric_params
from packages.backtest.versioning import get_code_version
from packages.backtest.walkforward import WalkForwardResult, run_walk_forward
from packages.quant.strategies import STRATEGY_CLASSES
from packages.research import dsl
from packages.research.features import FeatureSignal, research_feature_signals
from packages.risk.config import RiskLimits

DEFAULT_MUTATION_PCT = 0.2
DEFAULT_POPULATION_SIZE = 6
DEFAULT_GENERATIONS = 3
DEFAULT_ELITE_COUNT = 2
# Same bound, same rationale as packages/backtest/optimize.py's MAX_COMBINATIONS:
# a runaway search can never silently burn unbounded compute.
MAX_SEARCH_EVALUATIONS = 30


def mutate_params(rng: random.Random, base_params: dict, *, max_pct: float = DEFAULT_MUTATION_PCT) -> dict:
    mutated: dict = {}
    for key, original in base_params.items():
        factor = 1.0 + rng.uniform(-max_pct, max_pct)
        value = original * factor
        if isinstance(original, int):
            value = max(1, round(value))
        mutated[key] = value
    return mutated


def crossover_params(rng: random.Random, parent_a: dict, parent_b: dict) -> dict:
    """Uniform crossover: each parameter independently inherited from
    either parent, keeping the search "genetic" rather than pure hill-
    climbing around a single elite."""
    return {key: rng.choice([parent_a[key], parent_b[key]]) for key in parent_a}


def describe_changes(parent_params: dict, child_params: dict) -> list[str]:
    """Human-readable diff for `StrategyVersion.changes` — never a
    fabricated summary, just the literal before/after per changed param."""
    changes = []
    for key, new_value in child_params.items():
        old_value = parent_params.get(key)
        if old_value is None or old_value == new_value:
            continue
        pct = ((new_value - old_value) / old_value * 100) if old_value else None
        pct_str = f"{pct:+.1f}%" if pct is not None else "n/a"
        changes.append(f"{key}: {old_value} -> {new_value} ({pct_str})")
    return changes


@dataclass(frozen=True)
class Individual:
    params: dict
    walk_forward: WalkForwardResult
    fitness: float | None
    consistent: bool | None


@dataclass(frozen=True)
class GenerationSummary:
    generation: int
    population: list[Individual]
    best: Individual | None


@dataclass(frozen=True)
class GeneticSearchResult:
    strategy_code: str
    generations: list[GenerationSummary]
    best: Individual | None
    total_evaluations: int
    reason: str
    reproducibility: dict


def _pooled_expectancy(wf: WalkForwardResult) -> float | None:
    all_r = [t["r_multiple"] for w in wf.windows for t in w.result.trades if t["r_multiple"] is not None]
    if not all_r:
        return None
    return sum(all_r) / len(all_r)


def _rank_key(individual: Individual) -> tuple[bool, float]:
    return (individual.consistent is True, individual.fitness if individual.fitness is not None else float("-inf"))


def run_genetic_search(
    db: Session, *, strategy_code: str, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, window_days: float, initial_capital: float,
    population_size: int = DEFAULT_POPULATION_SIZE, generations: int = DEFAULT_GENERATIONS,
    mutation_pct: float = DEFAULT_MUTATION_PCT, elite_count: int = DEFAULT_ELITE_COUNT,
    seed: int = 42, risk_limits: RiskLimits | None = None, max_evaluations: int = MAX_SEARCH_EVALUATIONS,
) -> GeneticSearchResult:
    if population_size < 1 or generations < 1:
        raise ValueError("population_size and generations must be >= 1")
    total = population_size * generations
    if total > max_evaluations:
        raise ValueError(f"population_size x generations ({total}) exceeds max_evaluations ({max_evaluations})")

    strategy_class = STRATEGY_CLASSES.get(strategy_code)
    if strategy_class is None:
        raise ValueError(f"unknown strategy code: {strategy_code!r}")

    base_params = numeric_params(strategy_class())
    rng = random.Random(seed)

    def _evaluate(params: dict) -> Individual:
        strategy = strategy_class(**params)
        wf = run_walk_forward(
            db, strategy=strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts, window_days=window_days, initial_capital=initial_capital,
            risk_limits=risk_limits,
        )
        return Individual(params=params, walk_forward=wf, fitness=_pooled_expectancy(wf), consistent=wf.consistent)

    population_params = [dict(base_params)] + [
        mutate_params(rng, base_params, max_pct=mutation_pct) for _ in range(population_size - 1)
    ]
    generation_summaries: list[GenerationSummary] = []
    all_individuals: list[Individual] = []

    for gen_index in range(generations):
        population = [_evaluate(p) for p in population_params]
        all_individuals.extend(population)
        ranked = sorted(population, key=_rank_key, reverse=True)
        best = ranked[0] if ranked and ranked[0].fitness is not None else None
        generation_summaries.append(GenerationSummary(generation=gen_index, population=population, best=best))

        if gen_index == generations - 1:
            break
        elites = ranked[: max(1, elite_count)]
        next_population = [e.params for e in elites]
        while len(next_population) < population_size:
            if len(elites) >= 2 and rng.random() < 0.5:
                parent_a, parent_b = rng.sample(elites, 2)
                child = crossover_params(rng, parent_a.params, parent_b.params)
            else:
                child = mutate_params(rng, rng.choice(elites).params, max_pct=mutation_pct)
            next_population.append(child)
        population_params = next_population

    consistent_individuals = [i for i in all_individuals if i.consistent is True]
    if not consistent_individuals:
        best_overall = None
        reason = (
            f"none of {len(all_individuals)} evaluated candidates across {generations} generations "
            "passed the walk-forward consistency bar"
        )
    else:
        best_overall = max(consistent_individuals, key=lambda i: i.fitness if i.fitness is not None else float("-inf"))
        reason = (
            f"best of {len(consistent_individuals)} consistent candidates "
            f"(of {len(all_individuals)} evaluated across {generations} generations) by pooled expectancy"
        )

    return GeneticSearchResult(
        strategy_code=strategy_code, generations=generation_summaries, best=best_overall,
        total_evaluations=len(all_individuals), reason=reason,
        reproducibility={"code_version": get_code_version(), "random_seed": seed, "timestamp": datetime.now(timezone.utc).isoformat()},
    )


@dataclass(frozen=True)
class FeatureFilterCandidate:
    feature_filter: dict
    source_signal: FeatureSignal
    rationale: str


def propose_feature_filter_candidates(signals: list[FeatureSignal], *, max_candidates: int = 3) -> list[FeatureFilterCandidate]:
    """Turns `packages.research.features.research_feature_signals()`
    output into structural DSL proposals. §23's "não assumir correlation =
    causation" discipline carries over: only patterns with a POSITIVE,
    NOT-regime-dependent observed expectancy are proposed at all, and every
    proposal is validated (`packages.research.dsl.validate`) before being
    handed back — a malformed filter never reaches a caller.
    """
    candidates = []
    ranked = sorted(
        (s for s in signals if s.expectancy is not None and s.expectancy > 0 and not s.regime_dependent),
        key=lambda s: s.expectancy if s.expectancy is not None else 0.0,
        reverse=True,
    )
    for signal in ranked[:max_candidates]:
        feature_filter = {"eq": ["regime", {"lit": signal.regime}]}
        validation = dsl.validate(feature_filter)
        if not validation.valid:
            continue
        candidates.append(
            FeatureFilterCandidate(
                feature_filter=feature_filter,
                source_signal=signal,
                rationale=(
                    f"pattern_type={signal.pattern_type!r} shows positive expectancy ({signal.expectancy:+.4f}R, "
                    f"n={signal.sample_size}) specifically in regime={signal.regime!r} and is not regime-dependent "
                    "(consistent expectancy sign across every regime it's been observed in)"
                ),
            )
        )
    return candidates


@dataclass(frozen=True)
class GeneratorProposal:
    kind: str  # "parameter_mutation" | "feature_filter"
    strategy_code: str
    params: dict
    dsl_definition: dict | None
    changes: list[str]
    evidence: dict


def propose_candidates(
    db: Session, *, strategy_code: str, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, window_days: float, initial_capital: float,
    run_genetic: bool = True, run_feature_filters: bool = True,
    genetic_kwargs: dict | None = None, risk_limits: RiskLimits | None = None,
) -> list[GeneratorProposal]:
    """StrategyGenerator's top-level entry point (§16-21). Returns
    UNPERSISTED proposals in ranked-by-family order — genetic search
    result first (if it found a consistent winner), then feature-filter
    proposals (if any). An empty list is honest: no run above the walk-
    forward consistency bar, or no non-regime-dependent feature evidence
    yet — never a fabricated candidate to fill the list.
    """
    proposals: list[GeneratorProposal] = []
    strategy_class = STRATEGY_CLASSES.get(strategy_code)
    if strategy_class is None:
        raise ValueError(f"unknown strategy code: {strategy_code!r}")
    base_params = numeric_params(strategy_class())

    if run_genetic:
        result = run_genetic_search(
            db, strategy_code=strategy_code, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts, window_days=window_days, initial_capital=initial_capital,
            risk_limits=risk_limits, **(genetic_kwargs or {}),
        )
        if result.best is not None:
            proposals.append(
                GeneratorProposal(
                    kind="parameter_mutation", strategy_code=strategy_code, params=result.best.params,
                    dsl_definition=None, changes=describe_changes(base_params, result.best.params),
                    evidence={
                        "fitness_pooled_expectancy": result.best.fitness, "consistent": result.best.consistent,
                        "total_evaluations": result.total_evaluations, "reason": result.reason,
                        "reproducibility": result.reproducibility,
                    },
                )
            )

    if run_feature_filters:
        signals = research_feature_signals(db)
        for candidate in propose_feature_filter_candidates(signals):
            proposals.append(
                GeneratorProposal(
                    kind="feature_filter", strategy_code=strategy_code, params=base_params,
                    dsl_definition=candidate.feature_filter, changes=[f"add feature_filter: {candidate.feature_filter}"],
                    evidence={"rationale": candidate.rationale, "sample_size": candidate.source_signal.sample_size},
                )
            )

    return proposals
