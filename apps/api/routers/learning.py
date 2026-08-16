from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import MarketMemoryOut, StrategyLearningOut, TradeJournalOut
from packages.quant.learning.memory import find_similar_contexts
from packages.shared.models import (
    AdminUser,
    Asset,
    MarketMemory,
    Position,
    StrategyPerformance,
    StrategyRow,
    Trade,
    TradeJournal,
)

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/strategy-performance", response_model=list[StrategyLearningOut])
def list_strategy_performance(
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[StrategyLearningOut]:
    strategies = db.query(StrategyRow).order_by(StrategyRow.code).all()
    results = []
    for strategy in strategies:
        perf = (
            db.query(StrategyPerformance)
            .filter(StrategyPerformance.strategy_id == strategy.id)
            .order_by(StrategyPerformance.as_of.desc())
            .first()
        )
        results.append(
            StrategyLearningOut(
                strategy_id=strategy.id,
                strategy_code=strategy.code,
                lifecycle_stage=strategy.lifecycle_stage,
                as_of=perf.as_of if perf else None,
                window_trades=perf.window_trades if perf else 0,
                total_trades=perf.total_trades if perf else 0,
                win_rate=perf.win_rate if perf else None,
                profit_factor=perf.profit_factor if perf else None,
                avg_win=perf.avg_win if perf else None,
                avg_loss=perf.avg_loss if perf else None,
                sharpe=perf.sharpe if perf else None,
                max_drawdown=perf.max_drawdown if perf else None,
                expectancy=perf.expectancy if perf else None,
                best_regime=perf.best_regime if perf else None,
                worst_regime=perf.worst_regime if perf else None,
                health_score=perf.health_score if perf else None,
            )
        )
    return results


@router.get("/trade-journal", response_model=list[TradeJournalOut])
def list_trade_journal(
    limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[TradeJournalOut]:
    rows = db.execute(
        select(TradeJournal, Trade, Position, Asset, StrategyRow)
        .join(Trade, Trade.id == TradeJournal.trade_id)
        .join(Position, Position.id == Trade.position_id)
        .join(Asset, Asset.id == Position.asset_id)
        .join(StrategyRow, StrategyRow.id == Position.strategy_id)
        .order_by(TradeJournal.created_at.desc())
        .limit(limit)
    ).all()
    return [
        TradeJournalOut(
            trade_id=trade.id, asset_symbol=asset.symbol, strategy_code=strategy.code,
            expected_outcome=journal.expected_outcome, actual_outcome=journal.actual_outcome,
            hypothesis=journal.hypothesis, root_cause=journal.root_cause, created_at=journal.created_at,
        )
        for journal, trade, _position, asset, strategy in rows
    ]


@router.get("/memory", response_model=list[MarketMemoryOut])
def list_market_memory(
    limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[MarketMemoryOut]:
    rows = db.execute(
        select(MarketMemory, Asset).outerjoin(Asset, Asset.id == MarketMemory.asset_id).order_by(MarketMemory.ts.desc()).limit(limit)
    ).all()
    return [
        MarketMemoryOut(id=memory.id, ts=memory.ts, asset_symbol=asset.symbol if asset else None, context=memory.context, outcome=memory.outcome)
        for memory, asset in rows
    ]


@router.get("/memory/similar", response_model=list[MarketMemoryOut])
def get_similar_contexts(
    regime: str | None = None,
    pattern_type: str | None = None,
    direction: str | None = None,
    k: int = 10,
    db: Session = Depends(get_session),
    _: AdminUser = Depends(get_current_admin),
) -> list[MarketMemoryOut]:
    rows = find_similar_contexts(db, regime=regime, pattern_type=pattern_type, direction=direction, k=k)
    asset_ids = {row.asset_id for row in rows if row.asset_id is not None}
    symbols = {a.id: a.symbol for a in db.query(Asset).filter(Asset.id.in_(asset_ids)).all()} if asset_ids else {}
    return [
        MarketMemoryOut(id=row.id, ts=row.ts, asset_symbol=symbols.get(row.asset_id), context=row.context, outcome=row.outcome)
        for row in rows
    ]
