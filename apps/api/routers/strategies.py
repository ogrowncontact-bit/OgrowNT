from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import StrategyOut, StrategyPerformanceOut, StrategyRestoreRequest
from packages.quant.learning.quarantine import restore_from_quarantine
from packages.shared.models import AdminUser, StrategyPerformance, StrategyRow

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyOut])
def list_strategies(db: Session = Depends(get_session)) -> list[StrategyRow]:
    return db.query(StrategyRow).order_by(StrategyRow.code).all()


@router.get("/{strategy_id}/performance", response_model=StrategyPerformanceOut)
def get_strategy_performance(strategy_id: int, db: Session = Depends(get_session)) -> StrategyPerformanceOut:
    strategy = db.get(StrategyRow, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")

    perf = (
        db.query(StrategyPerformance)
        .filter(StrategyPerformance.strategy_id == strategy_id)
        .order_by(StrategyPerformance.as_of.desc())
        .first()
    )
    if perf is None:
        # docs/blueprint/06-memory-system.md's Strategy Memory only exists
        # once a trade has closed (packages/quant/learning/strategy_stats.py,
        # invoked by apps/worker/trade_monitor.py on every close) — honestly
        # empty rather than a fabricated number until then.
        return StrategyPerformanceOut(
            strategy_id=strategy_id, total_trades=0, win_rate=None, profit_factor=None, expectancy=None,
            note="No trades closed yet for this strategy. Performance tracking begins once paper trades close.",
        )

    return StrategyPerformanceOut(
        strategy_id=strategy_id, total_trades=perf.total_trades, win_rate=perf.win_rate,
        profit_factor=perf.profit_factor, expectancy=perf.expectancy,
        note=f"Rolling window of the last {perf.window_trades} trades, as of {perf.as_of.isoformat()}. "
        "See /api/learning/strategy-performance for the full breakdown (health score, sharpe, drawdown, best/worst regime).",
    )


@router.post("/{strategy_id}/restore", response_model=StrategyOut)
def restore_strategy(
    strategy_id: int,
    payload: StrategyRestoreRequest = StrategyRestoreRequest(),
    db: Session = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
) -> StrategyRow:
    """Admin-only: bring a quarantined strategy back into live signal
    generation (packages/quant/learning/quarantine.py). Never automatic —
    quarantine is a one-way DET safety action; restoring it is always a
    deliberate human decision."""
    try:
        return restore_from_quarantine(db, strategy_id, to_stage=payload.to_stage, actor=admin.email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
