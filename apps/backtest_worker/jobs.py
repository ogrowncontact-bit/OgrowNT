"""BacktestJob dispatch — "PROMPT 7" §46-47. One function per job `kind`,
called from apps/backtest_worker/main.py's polling loop. Every branch is a
thin adapter from a JSON payload to the already-tested
packages/backtest/* engine functions; no new business logic lives here.

This module (and everything it imports) is READ/COMPUTE only per §65: it
never imports packages.execution's order-submission path, never mutates
`strategies`/`positions`/`orders`/`portfolio_snapshots`, and the one table
it writes to outside `backtest_jobs` itself (`backtest_runs`,
`monte_carlo_runs`, `stress_test_runs`) exists solely to record analysis
results.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.backtest.engine import run_backtest
from packages.backtest.monte_carlo import run_monte_carlo
from packages.backtest.optimize import optimize_parameters
from packages.backtest.persistence import persist_backtest_run, persist_monte_carlo_run, persist_stress_test_run
from packages.backtest.report import run_full_lab
from packages.backtest.sensitivity import run_capital_sensitivity, run_cost_sensitivity, run_slippage_sensitivity
from packages.backtest.stress_test import SCENARIOS, run_stress_scenario
from packages.backtest.walkforward import run_walk_forward
from packages.backtest.walkforward_optimization import run_walk_forward_optimization
from packages.quant.strategies import STRATEGY_CLASSES
from packages.shared.models import Asset, BacktestJob, BacktestRun, StrategyRow


def _resolve_strategy_asset(db: Session, payload: dict) -> tuple[StrategyRow, Asset]:
    strategy_row = db.get(StrategyRow, payload["strategy_id"])
    if strategy_row is None:
        raise ValueError(f"strategy_id {payload['strategy_id']} not found")
    asset = db.get(Asset, payload["asset_id"])
    if asset is None:
        raise ValueError(f"asset_id {payload['asset_id']} not found")
    if strategy_row.code not in STRATEGY_CLASSES:
        raise ValueError(f"no backtest-capable strategy implementation registered for '{strategy_row.code}'")
    return strategy_row, asset


def _numeric_params(strategy) -> dict:
    return {k: v for k, v in vars(strategy).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _run_backtest_job(db: Session, payload: dict) -> dict:
    strategy_row, asset = _resolve_strategy_asset(db, payload)
    strategy = STRATEGY_CLASSES[strategy_row.code]()
    result = run_backtest(
        db, strategy=strategy, asset_id=asset.id, symbol=asset.symbol, timeframe=payload.get("timeframe", "1m"),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]), initial_capital=payload.get("initial_capital", 10_000.0),
    )
    run = persist_backtest_run(
        db, strategy_row=strategy_row, asset=asset, timeframe=payload.get("timeframe", "1m"), kind="backtest",
        group_label=None, window_index=None, total_windows=None, params=_numeric_params(strategy),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]), initial_capital=payload.get("initial_capital", 10_000.0), result=result,
    )
    return {"backtest_run_id": run.id, "num_trades": result.num_trades, "net_return": result.net_return}


def _run_walk_forward_job(db: Session, payload: dict) -> dict:
    strategy_row, asset = _resolve_strategy_asset(db, payload)
    strategy = STRATEGY_CLASSES[strategy_row.code]()
    wf = run_walk_forward(
        db, strategy=strategy, asset_id=asset.id, symbol=asset.symbol, timeframe=payload.get("timeframe", "1m"),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]), window_days=payload["window_days"],
        initial_capital=payload.get("initial_capital", 10_000.0),
    )
    run_ids = []
    for window in wf.windows:
        run = persist_backtest_run(
            db, strategy_row=strategy_row, asset=asset, timeframe=payload.get("timeframe", "1m"), kind="walk_forward_window",
            group_label=f"job-wf-{payload.get('_job_id', 'na')}", window_index=window.index, total_windows=len(wf.windows),
            params=_numeric_params(strategy), start_ts=window.start_ts, end_ts=window.end_ts,
            initial_capital=payload.get("initial_capital", 10_000.0), result=window.result,
        )
        run_ids.append(run.id)
    return {"backtest_run_ids": run_ids, "consistent": wf.consistent, "reason": wf.reason}


def _run_walk_forward_optimization_job(db: Session, payload: dict) -> dict:
    strategy_row, asset = _resolve_strategy_asset(db, payload)
    wf = run_walk_forward_optimization(
        db, strategy_code=strategy_row.code, asset_id=asset.id, symbol=asset.symbol, timeframe=payload.get("timeframe", "1m"),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]), train_days=payload["train_days"],
        validation_days=payload["validation_days"], initial_capital=payload.get("initial_capital", 10_000.0),
    )
    return {
        "num_windows": len(wf.windows), "pooled_oos_expectancy": wf.pooled_oos_expectancy,
        "oos_positive_window_ratio": wf.oos_positive_window_ratio, "consistent": wf.consistent, "reason": wf.reason,
        "parameter_stability": wf.parameter_stability,
        "windows": [
            {"index": w.index, "best_params": w.best_params, "validation_num_trades": w.validation_result.num_trades, "validation_expectancy": w.validation_result.expectancy}
            for w in wf.windows
        ],
    }


def _run_optimize_job(db: Session, payload: dict) -> dict:
    strategy_row, asset = _resolve_strategy_asset(db, payload)
    kwargs: dict = {}
    if payload.get("multipliers"):
        kwargs["multipliers"] = tuple(payload["multipliers"])
    if payload.get("max_combinations"):
        kwargs["max_combinations"] = payload["max_combinations"]
    opt = optimize_parameters(
        db, strategy_code=strategy_row.code, asset_id=asset.id, symbol=asset.symbol, timeframe=payload.get("timeframe", "1m"),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]), window_days=payload["window_days"],
        initial_capital=payload.get("initial_capital", 10_000.0), **kwargs,
    )
    return {
        "num_candidates": len(opt.candidates), "best_params": opt.best.params if opt.best else None, "reason": opt.reason,
    }


def _run_monte_carlo_job(db: Session, payload: dict) -> dict:
    reference = db.get(BacktestRun, payload["backtest_run_id"])
    if reference is None:
        raise ValueError(f"backtest_run_id {payload['backtest_run_id']} not found")
    output = run_monte_carlo(
        reference.trades, initial_capital=reference.initial_capital, method=payload.get("method", "trade_reshuffling"),
        num_simulations=payload.get("num_simulations", 1000), random_seed=payload.get("random_seed", 42),
        drawdown_threshold_pct=payload.get("drawdown_threshold_pct"),
    )
    row = persist_monte_carlo_run(db, reference_backtest_run_id=reference.id, output=output)
    return {"monte_carlo_run_id": row.id, "probability_of_loss": output.probability_of_loss}


def _run_stress_test_job(db: Session, payload: dict) -> dict:
    strategy_row, asset = _resolve_strategy_asset(db, payload)
    strategy_class = STRATEGY_CLASSES[strategy_row.code]
    reference = run_backtest(
        db, strategy=strategy_class(), asset_id=asset.id, symbol=asset.symbol, timeframe=payload.get("timeframe", "1m"),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]), initial_capital=payload.get("initial_capital", 10_000.0),
    )
    reference_run = persist_backtest_run(
        db, strategy_row=strategy_row, asset=asset, timeframe=payload.get("timeframe", "1m"), kind="backtest",
        group_label=None, window_index=None, total_windows=None, params=_numeric_params(strategy_class()),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]), initial_capital=payload.get("initial_capital", 10_000.0), result=reference,
    )
    scenarios = payload.get("scenarios") or list(SCENARIOS)
    row_ids = []
    for scenario in scenarios:
        result = run_stress_scenario(
            db, scenario=scenario, strategy_factory=strategy_class, asset_id=asset.id, symbol=asset.symbol,
            timeframe=payload.get("timeframe", "1m"), start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]),
            initial_capital=payload.get("initial_capital", 10_000.0),
        )
        row = persist_stress_test_run(db, reference_backtest_run_id=reference_run.id, result=result)
        row_ids.append(row.id)
    return {"reference_backtest_run_id": reference_run.id, "stress_test_run_ids": row_ids}


def _run_sensitivity_job(db: Session, payload: dict) -> dict:
    strategy_row, asset = _resolve_strategy_asset(db, payload)
    strategy_class = STRATEGY_CLASSES[strategy_row.code]
    kind = payload.get("kind", "cost")
    timeframe = payload.get("timeframe", "1m")
    start_ts, end_ts = _parse_ts(payload["start_ts"]), _parse_ts(payload["end_ts"])

    if kind == "slippage":
        report = run_slippage_sensitivity(
            db, strategy=strategy_class(), asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts, initial_capital=payload.get("initial_capital", 10_000.0),
        )
    elif kind == "capital":
        report = run_capital_sensitivity(
            db, strategy=strategy_class(), asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts,
        )
    else:
        report = run_cost_sensitivity(
            db, strategy=strategy_class(), asset_id=asset.id, symbol=asset.symbol, timeframe=timeframe,
            start_ts=start_ts, end_ts=end_ts, initial_capital=payload.get("initial_capital", 10_000.0),
        )
    return {
        "kind": report.kind, "survives_all_levels": report.survives_all_levels,
        "points": [{"level": p.level, "net_return": p.result.net_return, "survived": p.survived} for p in report.points],
    }


def _run_full_lab_job(db: Session, payload: dict) -> dict:
    strategy_row, asset = _resolve_strategy_asset(db, payload)
    return run_full_lab(
        db, strategy_row=strategy_row, asset=asset, timeframe=payload.get("timeframe", "1m"),
        start_ts=_parse_ts(payload["start_ts"]), end_ts=_parse_ts(payload["end_ts"]), initial_capital=payload.get("initial_capital", 10_000.0),
        monte_carlo_simulations=payload.get("monte_carlo_simulations", 300), random_seed=payload.get("random_seed", 42),
    )


_DISPATCH = {
    "backtest": _run_backtest_job,
    "walk_forward": _run_walk_forward_job,
    "walk_forward_optimization": _run_walk_forward_optimization_job,
    "optimize": _run_optimize_job,
    "monte_carlo": _run_monte_carlo_job,
    "stress_test": _run_stress_test_job,
    "sensitivity": _run_sensitivity_job,
    "full_lab": _run_full_lab_job,
}


def run_pending_jobs(db: Session, *, max_jobs_per_cycle: int = 1) -> int:
    """Dequeues up to `max_jobs_per_cycle` QUEUED jobs, oldest first, and
    executes each synchronously. One job at a time by default -- this
    process has no reason to parallelize heavy backtest compute against a
    single Postgres connection, and a private single-user system has no
    queue depth to justify the complexity."""
    jobs = db.query(BacktestJob).filter(BacktestJob.status == "queued").order_by(BacktestJob.created_at.asc()).limit(max_jobs_per_cycle).all()
    for job in jobs:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        job_id = job.id

        handler = _DISPATCH.get(job.kind)
        try:
            if handler is None:
                raise ValueError(f"unknown job kind: {job.kind!r}")
            payload = dict(job.payload)
            payload["_job_id"] = job_id
            result = handler(db, payload)
            job.status = "completed"
            job.result = result
        except Exception as exc:  # noqa: BLE001 - isolate this job, keep the loop alive for the next one
            db.rollback()
            reloaded = db.get(BacktestJob, job_id)
            assert reloaded is not None  # the row we just committed above can't have vanished
            job = reloaded
            job.status = "failed"
            job.error = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
    return len(jobs)
