from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_session
from apps.api.schemas import StrategyOut, StrategyPerformanceOut
from packages.shared.models import StrategyRow

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyOut])
def list_strategies(db: Session = Depends(get_session)) -> list[StrategyRow]:
    return db.query(StrategyRow).order_by(StrategyRow.code).all()


@router.get("/{strategy_id}/performance", response_model=StrategyPerformanceOut)
def get_strategy_performance(strategy_id: int, db: Session = Depends(get_session)) -> StrategyPerformanceOut:
    strategy = db.get(StrategyRow, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")

    # strategy_performance (docs/blueprint/02-database-schema.md) is populated
    # from closed trades, which requires the Execution Engine (Phase 3) and
    # enough sample size (docs/blueprint/10-backtesting-paper-trading.md). No
    # trade has ever been executed yet, so this is honestly empty rather than
    # a fabricated number.
    return StrategyPerformanceOut(
        strategy_id=strategy_id,
        total_trades=0,
        win_rate=None,
        profit_factor=None,
        expectancy=None,
        note="No trades yet — Execution Engine (Fase 3) has not run. Performance "
        "tracking begins once paper trades close.",
    )
