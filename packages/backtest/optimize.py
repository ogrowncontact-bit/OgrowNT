"""Parameter optimization — docs/blueprint/12-roadmap.md Phase 7's
"otimização de parâmetros". A bounded grid search over a strategy's
numeric parameters, each candidate judged the same way
packages/backtest/walkforward.py judges any strategy: walk-forward
consistency across time, never a single lucky backtest window.

Never applies anything: returns a ranked report. A human decides whether
to actually change a strategy's live parameters (today hardcoded defaults
in packages/quant/strategies/*.py's constructor defaults), so a runaway
search can never silently rewrite live trading logic — the same
"DET proposes, nothing auto-applies" discipline as
packages/quant/learning/promotion.py and packages/quant/learning/research.py.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from packages.backtest.walkforward import WalkForwardResult, run_walk_forward
from packages.quant.strategies import STRATEGY_CLASSES
from packages.risk.config import RiskLimits

DEFAULT_MULTIPLIERS: tuple[float, ...] = (0.7, 1.0, 1.3)
# Grids grow combinatorially with parameter count; bound the total number of
# walk-forward runs a single optimization call can trigger. The base/default
# parameter set is always included, the rest sampled deterministically.
MAX_COMBINATIONS = 30
_SAMPLE_SEED_PREFIX = "ogrownt-optimize"


@dataclass(frozen=True)
class OptimizationCandidate:
    params: dict
    walk_forward: WalkForwardResult


@dataclass(frozen=True)
class OptimizationResult:
    candidates: list[OptimizationCandidate]
    best: OptimizationCandidate | None
    reason: str


def numeric_params(strategy) -> dict:
    return {k: v for k, v in vars(strategy).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def build_param_grid(base_params: dict, multipliers: tuple[float, ...]) -> list[dict]:
    keys = list(base_params.keys())
    value_options = []
    for key in keys:
        original = base_params[key]
        options: list[float | int] = []
        seen = set()
        for m in multipliers:
            value = original * m
            if isinstance(original, int):
                value = max(1, round(value))
            if value not in seen:
                seen.add(value)
                options.append(value)
        value_options.append(options)

    return [dict(zip(keys, values, strict=True)) for values in itertools.product(*value_options)]


def _pooled_expectancy(wf: WalkForwardResult) -> float | None:
    all_r = [t["r_multiple"] for w in wf.windows for t in w.result.trades if t["r_multiple"] is not None]
    if not all_r:
        return None
    return sum(all_r) / len(all_r)


def optimize_parameters(
    db: Session, *, strategy_code: str, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, window_days: float, initial_capital: float,
    multipliers: tuple[float, ...] = DEFAULT_MULTIPLIERS, max_combinations: int = MAX_COMBINATIONS,
    risk_limits: RiskLimits | None = None,
) -> OptimizationResult:
    strategy_class = STRATEGY_CLASSES.get(strategy_code)
    if strategy_class is None:
        raise ValueError(f"unknown strategy code: {strategy_code!r}")

    base_params = numeric_params(strategy_class())
    combos = build_param_grid(base_params, multipliers)

    if len(combos) > max_combinations:
        rng = random.Random(f"{_SAMPLE_SEED_PREFIX}:{strategy_code}")
        others = [c for c in combos if c != base_params]
        sampled = rng.sample(others, k=min(max_combinations - 1, len(others)))
        combos = [dict(base_params), *sampled]

    candidates: list[OptimizationCandidate] = []
    for params in combos:
        strategy = strategy_class(**params)
        wf = run_walk_forward(
            db, strategy=strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts, window_days=window_days, initial_capital=initial_capital,
            risk_limits=risk_limits,
        )
        candidates.append(OptimizationCandidate(params=params, walk_forward=wf))

    consistent = [c for c in candidates if c.walk_forward.consistent is True]
    if not consistent:
        return OptimizationResult(
            candidates=candidates, best=None,
            reason=f"none of {len(candidates)} candidate parameter sets passed the walk-forward consistency bar",
        )

    best = max(consistent, key=lambda c: _pooled_expectancy(c.walk_forward) or float("-inf"))
    return OptimizationResult(
        candidates=candidates, best=best,
        reason=f"best of {len(consistent)} consistent candidates (of {len(candidates)} tested) by pooled expectancy",
    )
