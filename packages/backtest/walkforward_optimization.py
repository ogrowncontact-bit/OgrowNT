"""True walk-forward *optimization* — "PROMPT 7" §18-19's literal
TRAIN WINDOW -> OPTIMIZE -> VALIDATION WINDOW -> MOVE WINDOW -> ... flow.

Distinct from the two walk-forward-adjacent modules that already existed
before this phase, on purpose:
- packages/backtest/walkforward.py runs the strategy's *fixed* (default)
  parameters across a series of windows and checks the edge holds up over
  time -- no train step, by its own docstring's admission (our strategies'
  constants weren't fitted parameters, historically).
- packages/backtest/optimize.py grid-searches parameters once, judged by
  walkforward.py's whole-period consistency check -- global search, not a
  rolling train/validate split.

This module is the missing third piece: for each window, parameters are
selected using *only* that window's TRAIN slice, then evaluated on the very
next VALIDATION slice the optimizer never saw -- the literal in-sample vs.
out-of-sample split §17-19 describe, repeated and rolled forward. It's more
expensive (one grid search per window, not one for the whole period), so
`max_combinations` stays intentionally small by default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from packages.backtest.engine import BacktestResult, run_backtest
from packages.backtest.execution_models import ExecutionConfig
from packages.backtest.optimize import DEFAULT_MULTIPLIERS, build_param_grid, numeric_params
from packages.quant.strategies import STRATEGY_CLASSES
from packages.risk.config import RiskLimits

MAX_COMBINATIONS_PER_WINDOW = 12


@dataclass(frozen=True)
class WalkForwardOptWindow:
    index: int
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    best_params: dict
    train_result: BacktestResult
    validation_result: BacktestResult


@dataclass(frozen=True)
class WalkForwardOptimizationResult:
    windows: list[WalkForwardOptWindow] = field(default_factory=list)
    pooled_oos_expectancy: float | None = None
    oos_positive_window_ratio: float | None = None
    parameter_stability: dict = field(default_factory=dict)
    consistent: bool | None = None
    reason: str = ""


def _pooled_expectancy(result: BacktestResult) -> float | None:
    r_multiples = [t["r_multiple"] for t in result.trades if t["r_multiple"] is not None]
    return sum(r_multiples) / len(r_multiples) if r_multiples else None


def _param_stability(windows: list[WalkForwardOptWindow]) -> dict:
    """How much the chosen 'best' parameter values varied window to window
    -- a parameter that lands on a wildly different value every window is
    evidence of instability distinct from (but related to)
    packages/backtest/stability.py's perturbation-based check."""
    if not windows:
        return {}
    keys = windows[0].best_params.keys()
    stability: dict = {}
    for key in keys:
        values = [w.best_params.get(key) for w in windows if key in w.best_params]
        numeric_values = [v for v in values if isinstance(v, (int, float))]
        if len(numeric_values) < 2:
            stability[key] = {"values": values, "coefficient_of_variation": None}
            continue
        mean = sum(numeric_values) / len(numeric_values)
        variance = sum((v - mean) ** 2 for v in numeric_values) / len(numeric_values)
        std = variance**0.5
        cv = round(std / mean, 4) if mean else None
        stability[key] = {"values": values, "coefficient_of_variation": cv}
    return stability


def run_walk_forward_optimization(
    db: Session, *, strategy_code: str, asset_id: int, symbol: str, timeframe: str,
    start_ts: datetime, end_ts: datetime, train_days: float, validation_days: float, initial_capital: float,
    multipliers: tuple[float, ...] = DEFAULT_MULTIPLIERS, max_combinations: int = MAX_COMBINATIONS_PER_WINDOW,
    risk_limits: RiskLimits | None = None, execution: ExecutionConfig | None = None,
) -> WalkForwardOptimizationResult:
    strategy_class = STRATEGY_CLASSES.get(strategy_code)
    if strategy_class is None:
        raise ValueError(f"unknown strategy code: {strategy_code!r}")

    train_delta = timedelta(days=train_days)
    validation_delta = timedelta(days=validation_days)
    base_params = numeric_params(strategy_class())
    combos = build_param_grid(base_params, multipliers)
    if len(combos) > max_combinations:
        combos = combos[:max_combinations] if base_params in combos[:max_combinations] else [base_params, *combos[:max_combinations - 1]]

    windows: list[WalkForwardOptWindow] = []
    cursor = start_ts
    index = 0

    while cursor + train_delta < end_ts:
        train_start, train_end = cursor, cursor + train_delta
        validation_end = min(train_end + validation_delta, end_ts)

        best_params = dict(base_params)
        best_train_result: BacktestResult | None = None
        best_expectancy = float("-inf")
        for params in combos:
            candidate_strategy = strategy_class(**params)
            train_result = run_backtest(
                db, strategy=candidate_strategy, asset_id=asset_id, symbol=symbol, timeframe=timeframe,
                start_ts=train_start, end_ts=train_end, initial_capital=initial_capital,
                risk_limits=risk_limits, execution=execution,
            )
            expectancy = train_result.expectancy
            if expectancy is not None and expectancy > best_expectancy:
                best_expectancy = expectancy
                best_params = params
                best_train_result = train_result

        if best_train_result is None:
            # No candidate produced a single trade in TRAIN -- fall back to
            # the base params so VALIDATION still has something to report,
            # rather than silently skipping the window.
            best_train_result = run_backtest(
                db, strategy=strategy_class(**base_params), asset_id=asset_id, symbol=symbol, timeframe=timeframe,
                start_ts=train_start, end_ts=train_end, initial_capital=initial_capital,
                risk_limits=risk_limits, execution=execution,
            )

        # VALIDATION never influences parameter choice -- it only judges the
        # already-fixed best_params, per §17's "não permitir que o sistema
        # utilize TEST/VALIDATION durante otimização".
        validation_result = run_backtest(
            db, strategy=strategy_class(**best_params), asset_id=asset_id, symbol=symbol, timeframe=timeframe,
            start_ts=train_end, end_ts=validation_end, initial_capital=initial_capital,
            risk_limits=risk_limits, execution=execution,
        )

        windows.append(
            WalkForwardOptWindow(
                index=index, train_start=train_start, train_end=train_end,
                validation_start=train_end, validation_end=validation_end,
                best_params=best_params, train_result=best_train_result, validation_result=validation_result,
            )
        )
        cursor = validation_end
        index += 1

    if not windows:
        return WalkForwardOptimizationResult(
            windows=[], reason=f"period too short for even one train({train_days}d)+validation({validation_days}d) window",
        )

    all_oos_r = [t["r_multiple"] for w in windows for t in w.validation_result.trades if t["r_multiple"] is not None]
    tradeable = [w for w in windows if w.validation_result.num_trades > 0]
    pooled_oos_expectancy = sum(all_oos_r) / len(all_oos_r) if all_oos_r else None
    positive_windows = sum(1 for w in tradeable if w.validation_result.expectancy is not None and w.validation_result.expectancy > 0)
    oos_ratio = positive_windows / len(tradeable) if tradeable else None

    if len(all_oos_r) < 5:
        consistent = None
        reason = f"only {len(all_oos_r)} pooled out-of-sample trades across {len(windows)} windows -- too few to judge"
    else:
        consistent = pooled_oos_expectancy is not None and pooled_oos_expectancy > 0 and (oos_ratio or 0) >= 0.5
        reason = (
            f"pooled OOS expectancy={pooled_oos_expectancy:.4f}R over {len(all_oos_r)} trades, "
            f"{positive_windows}/{len(tradeable)} validation windows positive"
        )

    return WalkForwardOptimizationResult(
        windows=windows, pooled_oos_expectancy=pooled_oos_expectancy, oos_positive_window_ratio=oos_ratio,
        parameter_stability=_param_stability(windows), consistent=consistent, reason=reason,
    )
