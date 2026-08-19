"""Shared BacktestRun/MonteCarloRun/StressTestRun persistence — used by both
apps/api/routers/backtests.py (synchronous, quick runs) and
apps/backtest_worker/jobs.py (async job dispatch), so there's exactly one
place that decides what a persisted row looks like. Lives in
packages/backtest, not either app: docs/blueprint/01-repo-structure.md's
dependency table lets both apps depend on packages/backtest, and neither
app is allowed to import the other directly.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from packages.backtest.engine import BacktestResult
from packages.backtest.monte_carlo import MonteCarloOutput
from packages.backtest.stress_test import StressScenarioResult
from packages.backtest.versioning import get_code_version
from packages.shared.models import Asset, BacktestRun, MonteCarloRun, StrategyRow, StressTestRun

# Mirrors backtest_jobs.kind's CHECK constraint (packages/shared/models.py) --
# shared here (not in apps/backtest_worker/jobs.py) so apps/api can validate
# a BacktestJobCreate payload without importing apps/backtest_worker (apps
# never import each other directly, matching apps/api's existing rule
# against importing apps/worker).
JOB_KINDS = ("backtest", "walk_forward", "walk_forward_optimization", "optimize", "monte_carlo", "stress_test", "sensitivity", "full_lab")


def persist_backtest_run(
    db: Session, *, strategy_row: StrategyRow, asset: Asset, timeframe: str, kind: str,
    group_label: str | None, window_index: int | None, total_windows: int | None, params: dict,
    start_ts: datetime, end_ts: datetime, initial_capital: float, result: BacktestResult,
    data_version: str | None = None,
) -> BacktestRun:
    run = BacktestRun(
        strategy_id=strategy_row.id, asset_id=asset.id, timeframe=timeframe, kind=kind,
        group_label=group_label, window_index=window_index, total_windows=total_windows, params=params,
        start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital,
        net_return=result.net_return, cagr_like_return=result.cagr_like_return, win_rate=result.win_rate,
        profit_factor=result.profit_factor, max_drawdown=result.max_drawdown, avg_trade=result.avg_trade,
        expectancy=result.expectancy, num_trades=result.num_trades, sharpe_like=result.sharpe_like,
        equity_curve=result.equity_curve, trades=result.trades, notes=result.notes,
        strategy_version=strategy_row.version, code_version=get_code_version(),
        data_version=data_version or result.data_fingerprint, extra_metrics=result.extra_metrics,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def persist_monte_carlo_run(db: Session, *, reference_backtest_run_id: int, output: MonteCarloOutput) -> MonteCarloRun:
    row = MonteCarloRun(
        reference_backtest_run_id=reference_backtest_run_id, method=output.method,
        num_simulations=output.num_simulations, random_seed=output.random_seed, percentiles=output.percentiles,
        probability_of_loss=output.probability_of_loss, probability_of_drawdown_threshold=output.probability_of_drawdown_threshold,
        drawdown_threshold_pct=output.drawdown_threshold_pct, notes=output.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def persist_stress_test_run(db: Session, *, reference_backtest_run_id: int, result: StressScenarioResult) -> StressTestRun:
    row = StressTestRun(
        reference_backtest_run_id=reference_backtest_run_id, scenario=result.scenario, params=result.params,
        result={
            "return_delta": result.return_delta, "drawdown_delta": result.drawdown_delta,
            "stressed_num_trades": result.stressed.num_trades, "stressed_net_return": result.stressed.net_return,
            "stressed_max_drawdown": result.stressed.max_drawdown, "notes": result.notes,
        },
        survived=result.survived,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
