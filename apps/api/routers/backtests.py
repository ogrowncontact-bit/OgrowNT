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
    BacktestRequest,
    BacktestSummaryOut,
    OptimizeCandidateOut,
    OptimizeRequest,
    OptimizeResponseOut,
    WalkForwardRequest,
    WalkForwardResponseOut,
)
from packages.backtest.engine import run_backtest
from packages.backtest.optimize import optimize_parameters
from packages.backtest.walkforward import run_walk_forward
from packages.quant.strategies import STRATEGY_CLASSES
from packages.shared.models import AdminUser, Asset, BacktestRun, StrategyRow

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


def _persist_run(
    db: Session, *, strategy_row: StrategyRow, asset: Asset, timeframe: str, kind: str,
    group_label: str | None, window_index: int | None, total_windows: int | None, params: dict,
    start_ts, end_ts, initial_capital: float, result,
) -> BacktestRun:
    run = BacktestRun(
        strategy_id=strategy_row.id, asset_id=asset.id, timeframe=timeframe, kind=kind,
        group_label=group_label, window_index=window_index, total_windows=total_windows, params=params,
        start_ts=start_ts, end_ts=end_ts, initial_capital=initial_capital,
        net_return=result.net_return, cagr_like_return=result.cagr_like_return, win_rate=result.win_rate,
        profit_factor=result.profit_factor, max_drawdown=result.max_drawdown, avg_trade=result.avg_trade,
        expectancy=result.expectancy, num_trades=result.num_trades, sharpe_like=result.sharpe_like,
        equity_curve=result.equity_curve, trades=result.trades, notes=result.notes,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _summary(run: BacktestRun, strategy_code: str, asset_symbol: str) -> BacktestSummaryOut:
    return BacktestSummaryOut(
        id=run.id, strategy_code=strategy_code, asset_symbol=asset_symbol, timeframe=run.timeframe,
        kind=run.kind, group_label=run.group_label, window_index=run.window_index, total_windows=run.total_windows,
        start_ts=run.start_ts, end_ts=run.end_ts, initial_capital=run.initial_capital, net_return=run.net_return,
        cagr_like_return=run.cagr_like_return, win_rate=run.win_rate, profit_factor=run.profit_factor,
        max_drawdown=run.max_drawdown, avg_trade=run.avg_trade, expectancy=run.expectancy, num_trades=run.num_trades,
        sharpe_like=run.sharpe_like, created_at=run.created_at,
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
    run = _persist_run(
        db, strategy_row=strategy_row, asset=asset, timeframe=payload.timeframe, kind="backtest",
        group_label=None, window_index=None, total_windows=None, params=_numeric_params(strategy),
        start_ts=payload.start_ts, end_ts=payload.end_ts, initial_capital=payload.initial_capital, result=result,
    )
    summary = _summary(run, strategy_row.code, asset.symbol)
    return BacktestDetailOut(**summary.model_dump(), params=run.params, equity_curve=run.equity_curve, trades=run.trades, notes=run.notes)


@router.get("", response_model=list[BacktestSummaryOut])
def list_backtests(strategy_id: int | None = None, limit: int = 20, db: Session = Depends(get_session)) -> list[BacktestSummaryOut]:
    query = db.query(BacktestRun)
    if strategy_id is not None:
        query = query.filter(BacktestRun.strategy_id == strategy_id)
    rows = query.order_by(BacktestRun.created_at.desc()).limit(limit).all()
    return [_summary(run, run.strategy.code, run.asset.symbol) for run in rows]


@router.get("/{run_id}", response_model=BacktestDetailOut)
def get_backtest(run_id: int, db: Session = Depends(get_session)) -> BacktestDetailOut:
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest run not found")
    summary = _summary(run, run.strategy.code, run.asset.symbol)
    return BacktestDetailOut(**summary.model_dump(), params=run.params, equity_curve=run.equity_curve, trades=run.trades, notes=run.notes)


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
        run = _persist_run(
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
            run = _persist_run(
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
