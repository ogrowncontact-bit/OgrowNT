"""Backtest/Research Lab endpoints — docs/blueprint/03-api-spec.md's
`/api/research/experiments/{id}` is the read side of this; POST here is the
concrete "run a backtest" action the blueprint doesn't fully spell out.
Mutating endpoints (running a backtest costs real compute time and this is
a private single-user system) are admin-gated like every other POST in this
API, even though nothing here can touch real capital.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import (
    BacktestDetailOut,
    BacktestJobCreate,
    BacktestJobOut,
    BacktestRequest,
    BacktestSummaryOut,
    DataIntegrityIssueOut,
    DataIntegrityReportOut,
    FailureVerdictOut,
    OptimizeCandidateOut,
    OptimizeRequest,
    OptimizeResponseOut,
    RealityGapOut,
    StrategyLabCompareRequest,
    StrategyLabComparisonRow,
    WalkForwardRequest,
    WalkForwardResponseOut,
)
from packages.backtest.data_integrity import check_data_integrity
from packages.backtest.engine import run_backtest
from packages.backtest.failure_detector import detect_strategy_failure
from packages.backtest.optimize import optimize_parameters
from packages.backtest.persistence import JOB_KINDS, persist_backtest_run
from packages.backtest.quality_score import compute_quality_score
from packages.backtest.reality_gap import analyze_reality_gap
from packages.backtest.robustness import compute_robustness_score
from packages.backtest.walkforward import run_walk_forward
from packages.quant.strategies import STRATEGY_CLASSES
from packages.shared.models import AdminUser, Asset, BacktestJob, BacktestRun, StrategyRow

router = APIRouter(prefix="/api/backtests", tags=["backtests"])


def _resolve(db: Session, strategy_id: int, asset_id: int) -> tuple[StrategyRow, Asset]:
    strategy_row = db.get(StrategyRow, strategy_id)
    if strategy_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    if strategy_row.code not in STRATEGY_CLASSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No backtest-capable strategy implementation registered for '{strategy_row.code}'",
        )
    return strategy_row, asset


def _numeric_params(strategy) -> dict:
    return {k: v for k, v in vars(strategy).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def _summary(run: BacktestRun, strategy_code: str, asset_symbol: str) -> BacktestSummaryOut:
    return BacktestSummaryOut(
        id=run.id, strategy_code=strategy_code, asset_symbol=asset_symbol, timeframe=run.timeframe,
        kind=run.kind, group_label=run.group_label, window_index=run.window_index, total_windows=run.total_windows,
        start_ts=run.start_ts, end_ts=run.end_ts, initial_capital=run.initial_capital, net_return=run.net_return,
        cagr_like_return=run.cagr_like_return, win_rate=run.win_rate, profit_factor=run.profit_factor,
        max_drawdown=run.max_drawdown, avg_trade=run.avg_trade, expectancy=run.expectancy, num_trades=run.num_trades,
        sharpe_like=run.sharpe_like, created_at=run.created_at, strategy_version=run.strategy_version,
        code_version=run.code_version, data_version=run.data_version, random_seed=run.random_seed,
    )


@router.post("", response_model=BacktestDetailOut)
def create_backtest(
    payload: BacktestRequest, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> BacktestDetailOut:
    strategy_row, asset = _resolve(db, payload.strategy_id, payload.asset_id)
    strategy = STRATEGY_CLASSES[strategy_row.code]()

    result = run_backtest(
        db, strategy=strategy, asset_id=asset.id, symbol=asset.symbol, timeframe=payload.timeframe,
        start_ts=payload.start_ts, end_ts=payload.end_ts, initial_capital=payload.initial_capital,
    )
    run = persist_backtest_run(
        db, strategy_row=strategy_row, asset=asset, timeframe=payload.timeframe, kind="backtest",
        group_label=None, window_index=None, total_windows=None, params=_numeric_params(strategy),
        start_ts=payload.start_ts, end_ts=payload.end_ts, initial_capital=payload.initial_capital, result=result,
    )
    summary = _summary(run, strategy_row.code, asset.symbol)
    return BacktestDetailOut(**summary.model_dump(), params=run.params, equity_curve=run.equity_curve, trades=run.trades, notes=run.notes, extra_metrics=run.extra_metrics)


@router.get("", response_model=list[BacktestSummaryOut])
def list_backtests(
    strategy_id: int | None = None, limit: int = 20,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[BacktestSummaryOut]:
    query = db.query(BacktestRun)
    if strategy_id is not None:
        query = query.filter(BacktestRun.strategy_id == strategy_id)
    rows = query.order_by(BacktestRun.created_at.desc()).limit(limit).all()
    return [_summary(run, run.strategy.code, run.asset.symbol) for run in rows]



# --- "PROMPT 7" ----------------------------------------------------------
# Registered here — before the generic GET /{run_id} below — on purpose:
# FastAPI/Starlette match routes in registration order, and {run_id}: int
# would otherwise structurally match a literal path like "/jobs" first
# (then fail int coercion with a 422) before ever trying these more
# specific routes. Every static/differently-shaped path in this phase
# (`/jobs`, `/jobs/{job_id}`, `/data-integrity`, `/reality-gap/{id}`,
# `/failure-check/{id}`, `/compare`) has to come before it.


@router.post("/data-integrity", response_model=DataIntegrityReportOut)
def run_data_integrity_check(
    payload: BacktestRequest, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> DataIntegrityReportOut:
    """§52 — the same check run_backtest() runs internally before every
    backtest, exposed standalone so the Strategy Lab UI can show
    BACKTEST_BLOCKED / issues before a user even presses run."""
    report = check_data_integrity(db, payload.asset_id, payload.timeframe, payload.start_ts, payload.end_ts)
    return DataIntegrityReportOut(
        blocked=report.blocked, status=report.status, bars_checked=report.bars_checked,
        issues=[DataIntegrityIssueOut(severity=i.severity, code=i.code, detail=i.detail) for i in report.issues],
    )


@router.get("/reality-gap/{strategy_id}", response_model=RealityGapOut)
def get_reality_gap(
    strategy_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> RealityGapOut:
    gap = analyze_reality_gap(db, strategy_id)
    return RealityGapOut(
        strategy_id=gap.strategy_id, reference_backtest_id=gap.reference_backtest_id,
        return_difference=gap.return_difference, win_rate_difference=gap.win_rate_difference,
        expectancy_difference=gap.expectancy_difference, drawdown_difference=gap.drawdown_difference,
        execution_difference=gap.execution_difference, notes=gap.notes,
    )


@router.get("/failure-check/{strategy_id}", response_model=FailureVerdictOut)
def get_failure_check(
    strategy_id: int, backtest_run_id: int | None = None,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> FailureVerdictOut:
    """§43 — advisory only (see packages/backtest/failure_detector.py's
    docstring): reports STRATEGY_OK/REJECTED/QUARANTINED, never mutates
    `strategies.lifecycle_stage` itself."""
    strategy_row = db.get(StrategyRow, strategy_id)
    if strategy_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")

    reference = (
        db.query(BacktestRun).filter(BacktestRun.id == backtest_run_id).first()
        if backtest_run_id is not None
        else db.query(BacktestRun).filter(BacktestRun.strategy_id == strategy_id, BacktestRun.kind == "backtest").order_by(BacktestRun.created_at.desc()).first()
    )
    gap = analyze_reality_gap(db, strategy_id)

    verdict = detect_strategy_failure(
        expectancy=reference.expectancy if reference else None,
        max_drawdown_pct=reference.max_drawdown if reference else None,
        max_drawdown_limit_pct=20.0, reality_gap=gap,
    )
    return FailureVerdictOut(strategy_id=strategy_id, verdict=verdict.verdict, reasons=verdict.reasons)


@router.post("/compare", response_model=list[StrategyLabComparisonRow])
def compare_backtest_runs(
    payload: StrategyLabCompareRequest, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[StrategyLabComparisonRow]:
    """§16 — StrategyLab comparison table across arbitrary backtest runs
    (e.g. one reference run per candidate strategy: BREAKOUT vs MOMENTUM vs
    TREND FOLLOWING vs MEAN REVERSION)."""
    rows: list[StrategyLabComparisonRow] = []
    for run_id in payload.backtest_run_ids:
        run = db.get(BacktestRun, run_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backtest run {run_id} not found")
        robustness = compute_robustness_score(
            max_drawdown_pct=run.max_drawdown, num_trades=run.num_trades,
            regime_breakdown=(run.extra_metrics or {}).get("regime_breakdown"),
        )
        quality = compute_quality_score(expectancy=run.expectancy, num_trades=run.num_trades, robustness=robustness)
        rows.append(
            StrategyLabComparisonRow(
                strategy_id=run.strategy_id, strategy_code=run.strategy.code, net_return=run.net_return,
                max_drawdown=run.max_drawdown, expectancy=run.expectancy, profit_factor=run.profit_factor,
                sharpe_like=run.sharpe_like, num_trades=run.num_trades, quality_score=quality.score, status=quality.status,
            )
        )
    return rows


@router.post("/jobs", response_model=BacktestJobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: BacktestJobCreate, db: Session = Depends(get_session), admin: AdminUser = Depends(get_current_admin),
) -> BacktestJobOut:
    """§46-47 — queues a heavy analysis (walk_forward_optimization,
    monte_carlo, stress_test, sensitivity, full_lab) for
    apps/backtest_worker to pick up on its own process/cadence, instead of
    blocking this request. `backtest`/`walk_forward`/`optimize` also work
    here for consistency, though they usually run fast enough on this
    deployment's short mock-data window to use the synchronous endpoints
    above directly."""
    if payload.kind not in JOB_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown job kind '{payload.kind}' (expected one of {JOB_KINDS})")
    job = BacktestJob(kind=payload.kind, payload=payload.payload, status="queued", requested_by=admin.email)
    db.add(job)
    db.commit()
    db.refresh(job)
    return BacktestJobOut(
        id=job.id, kind=job.kind, status=job.status, payload=job.payload, result=job.result,
        error=job.error, created_at=job.created_at, started_at=job.started_at, completed_at=job.completed_at,
    )


@router.get("/jobs", response_model=list[BacktestJobOut])
def list_jobs(
    status_filter: str | None = None, limit: int = 20,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[BacktestJobOut]:
    query = db.query(BacktestJob)
    if status_filter is not None:
        query = query.filter(BacktestJob.status == status_filter)
    rows = query.order_by(BacktestJob.created_at.desc()).limit(limit).all()
    return [
        BacktestJobOut(id=j.id, kind=j.kind, status=j.status, payload=j.payload, result=j.result, error=j.error, created_at=j.created_at, started_at=j.started_at, completed_at=j.completed_at)
        for j in rows
    ]


@router.get("/jobs/{job_id}", response_model=BacktestJobOut)
def get_job(job_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> BacktestJobOut:
    job = db.get(BacktestJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return BacktestJobOut(
        id=job.id, kind=job.kind, status=job.status, payload=job.payload, result=job.result,
        error=job.error, created_at=job.created_at, started_at=job.started_at, completed_at=job.completed_at,
    )


@router.post("/jobs/{job_id}/cancel", response_model=BacktestJobOut)
def cancel_job(job_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> BacktestJobOut:
    """Only a still-QUEUED job can be cancelled — a RUNNING one is already
    executing synchronously inside apps/backtest_worker and runs to
    completion (see that module's docstring: there is no mid-job interrupt).
    """
    job = db.get(BacktestJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "queued":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"job is '{job.status}', only a queued job can be cancelled")
    job.status = "cancelled"
    db.add(job)
    db.commit()
    db.refresh(job)
    return BacktestJobOut(
        id=job.id, kind=job.kind, status=job.status, payload=job.payload, result=job.result,
        error=job.error, created_at=job.created_at, started_at=job.started_at, completed_at=job.completed_at,
    )


# --- end "PROMPT 7" static-path routes ------------------------------------


@router.get("/{run_id}", response_model=BacktestDetailOut)
def get_backtest(
    run_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> BacktestDetailOut:
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest run not found")
    summary = _summary(run, run.strategy.code, run.asset.symbol)
    return BacktestDetailOut(**summary.model_dump(), params=run.params, equity_curve=run.equity_curve, trades=run.trades, notes=run.notes, extra_metrics=run.extra_metrics)


@router.post("/walkforward", response_model=WalkForwardResponseOut)
def create_walk_forward(
    payload: WalkForwardRequest, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> WalkForwardResponseOut:
    strategy_row, asset = _resolve(db, payload.strategy_id, payload.asset_id)
    strategy = STRATEGY_CLASSES[strategy_row.code]()
    params = _numeric_params(strategy)

    wf_result = run_walk_forward(
        db, strategy=strategy, asset_id=asset.id, symbol=asset.symbol, timeframe=payload.timeframe,
        start_ts=payload.start_ts, end_ts=payload.end_ts, window_days=payload.window_days,
        initial_capital=payload.initial_capital,
    )

    group_label = f"wf-{uuid.uuid4().hex[:12]}"
    total_windows = len(wf_result.windows)
    summaries = []
    for window in wf_result.windows:
        run = persist_backtest_run(
            db, strategy_row=strategy_row, asset=asset, timeframe=payload.timeframe, kind="walk_forward_window",
            group_label=group_label, window_index=window.index, total_windows=total_windows, params=params,
            start_ts=window.start_ts, end_ts=window.end_ts, initial_capital=payload.initial_capital, result=window.result,
        )
        summaries.append(_summary(run, strategy_row.code, asset.symbol))

    return WalkForwardResponseOut(group_label=group_label, windows=summaries, consistent=wf_result.consistent, reason=wf_result.reason)


@router.post("/optimize", response_model=OptimizeResponseOut)
def create_optimization(
    payload: OptimizeRequest, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> OptimizeResponseOut:
    """Bounded grid-search parameter optimization. Every candidate is judged by
    the same walk-forward consistency bar as `/walkforward`, and each
    candidate's windows are persisted the same way — this endpoint only ever
    reports a ranked result, it never touches a strategy's live/default
    parameters (see packages/backtest/optimize.py's docstring).
    """
    strategy_row, asset = _resolve(db, payload.strategy_id, payload.asset_id)

    kwargs: dict = {}
    if payload.multipliers is not None:
        kwargs["multipliers"] = tuple(payload.multipliers)
    if payload.max_combinations is not None:
        kwargs["max_combinations"] = payload.max_combinations

    opt_result = optimize_parameters(
        db, strategy_code=strategy_row.code, asset_id=asset.id, symbol=asset.symbol, timeframe=payload.timeframe,
        start_ts=payload.start_ts, end_ts=payload.end_ts, window_days=payload.window_days,
        initial_capital=payload.initial_capital, **kwargs,
    )

    candidate_outs: list[OptimizeCandidateOut] = []
    for candidate in opt_result.candidates:
        group_label = f"opt-{uuid.uuid4().hex[:12]}"
        wf = candidate.walk_forward
        total_windows = len(wf.windows)
        summaries = []
        for window in wf.windows:
            run = persist_backtest_run(
                db, strategy_row=strategy_row, asset=asset, timeframe=payload.timeframe, kind="walk_forward_window",
                group_label=group_label, window_index=window.index, total_windows=total_windows, params=candidate.params,
                start_ts=window.start_ts, end_ts=window.end_ts, initial_capital=payload.initial_capital, result=window.result,
            )
            summaries.append(_summary(run, strategy_row.code, asset.symbol))
        candidate_outs.append(
            OptimizeCandidateOut(
                params=candidate.params, group_label=group_label, windows=summaries,
                consistent=wf.consistent, walk_forward_reason=wf.reason,
            )
        )

    best_params = opt_result.best.params if opt_result.best is not None else None
    return OptimizeResponseOut(candidates=candidate_outs, best_params=best_params, reason=opt_result.reason)

