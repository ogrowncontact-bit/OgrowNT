"""Parameter stability — docs/blueprint/10-backtesting-paper-trading.md's
anti-overfitting technique #4: perturbing a strategy's numeric parameters
by a small amount should not flip its backtest verdict from profitable to
unprofitable (or vice versa). If it does, the "edge" was fit to noise at
this exact parameter value, not a real market effect — the kind of thing
the blueprint calls out by name ("comprar às 14:37:12 de terça-feira").

Only possible because packages/quant/strategies/*.py's numeric constants
are constructor parameters (defaulting to the original module-level
constants) rather than hardcoded — see trend_following.py's class
docstring for why that refactor happened.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from packages.backtest.engine import BacktestResult, run_backtest
from packages.quant.strategies import STRATEGY_CLASSES
from packages.risk.config import RiskLimits

DEFAULT_PERTURBATION_PCT = 0.2  # +/-20% on each numeric parameter, one at a time


@dataclass(frozen=True)
class ParamRun:
    params: dict
    result: BacktestResult


@dataclass(frozen=True)
class StabilityResult:
    base: ParamRun
    perturbed: list[ParamRun]
    stable: bool | None  # None when there isn't enough data (on either side) to judge
    reason: str


def _numeric_params(strategy) -> dict:
    return {k: v for k, v in vars(strategy).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def _perturb(base_params: dict, key: str, factor: float) -> dict:
    perturbed = dict(base_params)
    original = base_params[key]
    new_value = original * factor
    if isinstance(original, int):
        new_value = max(1, round(new_value))
    perturbed[key] = new_value
    return perturbed


def _verdict(base: ParamRun, perturbed: list[ParamRun]) -> StabilityResult:
    if base.result.expectancy is None or base.result.num_trades == 0:
        return StabilityResult(base=base, perturbed=perturbed, stable=None, reason="base run produced no trades — nothing to test stability of")

    base_sign = base.result.expectancy > 0
    judged = [p for p in perturbed if p.result.expectancy is not None and p.result.num_trades > 0]
    if not judged:
        return StabilityResult(base=base, perturbed=perturbed, stable=None, reason="no perturbed run produced any trades — cannot judge stability")

    flips = sum(1 for p in judged if p.result.expectancy is not None and (p.result.expectancy > 0) != base_sign)
    stable = flips == 0
    reason = f"{flips}/{len(judged)} perturbed parameter runs flipped the expectancy sign vs. the base run"
    return StabilityResult(base=base, perturbed=perturbed, stable=stable, reason=reason)


def check_parameter_stability(
    db: Session, *, strategy_code: str, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, initial_capital: float,
    perturbation_pct: float = DEFAULT_PERTURBATION_PCT, risk_limits: RiskLimits | None = None,
    base_params: dict | None = None,
) -> StabilityResult:
    """`base_params` (new, "PROMPT 10" §16-21): perturb around a specific
    candidate parameter set instead of the strategy class's own defaults —
    used by `packages/research/experiment.py`'s ExperimentEngine to check
    whether a proposed candidate's chosen parameters are a stable choice,
    not a knife-edge fit. Every existing caller leaves this None and gets
    the original, unchanged default-centered behavior.
    """
    strategy_class = STRATEGY_CLASSES.get(strategy_code)
    if strategy_class is None:
        raise ValueError(f"unknown strategy code: {strategy_code!r}")

    base_strategy = strategy_class(**base_params) if base_params else strategy_class()
    base_params = _numeric_params(base_strategy)
    base_result = run_backtest(
        db, strategy=base_strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
        start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits,
    )
    base_run = ParamRun(params=base_params, result=base_result)

    perturbed_runs: list[ParamRun] = []
    for key in base_params:
        for factor in (1 - perturbation_pct, 1 + perturbation_pct):
            params = _perturb(base_params, key, factor)
            strategy = strategy_class(**params)
            result = run_backtest(
                db, strategy=strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
                start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital, risk_limits=risk_limits,
            )
            perturbed_runs.append(ParamRun(params=params, result=result))

    return _verdict(base_run, perturbed_runs)
