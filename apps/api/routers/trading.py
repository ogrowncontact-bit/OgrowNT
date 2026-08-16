from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import (
    OpportunityDetailOut,
    OrderOut,
    PositionOut,
    RiskCheckOut,
    RiskDecisionOut,
    ScoreBreakdown,
    TradeOut,
    TradeWhyOut,
)
from packages.shared.market_data import get_latest_close
from packages.shared.models import (
    AdminUser,
    Asset,
    MarketRegime,
    OpportunityScore,
    Order,
    Position,
    RiskCheck,
    RiskDecision,
    Signal,
    StrategyRow,
    Trade,
)

router = APIRouter(tags=["trading"])


def _position_out(db: Session, position: Position, asset: Asset, strategy: StrategyRow) -> PositionOut:
    unrealized_pnl = position.unrealized_pnl
    if position.status == "open":
        price = get_latest_close(db, position.asset_id)
        if price is not None:
            direction_mult = 1 if position.direction == "long" else -1
            unrealized_pnl = (price - position.entry_price) * position.size * direction_mult
    return PositionOut(
        id=position.id,
        asset_symbol=asset.symbol,
        strategy_code=strategy.code,
        direction=position.direction,
        entry_price=position.entry_price,
        current_stop=position.current_stop,
        target_price=position.target_price,
        size=position.size,
        opened_at=position.opened_at,
        closed_at=position.closed_at,
        status=position.status,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=position.realized_pnl,
        exit_price=position.exit_price,
        exit_reason=position.exit_reason,
    )


@router.get("/api/positions", response_model=list[PositionOut])
def list_positions(
    status_filter: str = "open", db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[PositionOut]:
    query = db.query(Position)
    if status_filter in ("open", "closed"):
        query = query.filter(Position.status == status_filter)
    positions = query.order_by(Position.opened_at.desc()).all()

    out = []
    for position in positions:
        asset = db.get(Asset, position.asset_id)
        strategy = db.get(StrategyRow, position.strategy_id)
        out.append(_position_out(db, position, asset, strategy))
    return out


@router.get("/api/orders", response_model=list[OrderOut])
def list_orders(
    limit: int = 100, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[Order]:
    return db.execute(select(Order).order_by(Order.id.desc()).limit(limit)).scalars().all()


@router.get("/api/trades", response_model=list[TradeOut])
def list_trades(
    limit: int = 100, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[TradeOut]:
    rows = db.execute(
        select(Trade, Position, Asset, StrategyRow)
        .join(Position, Position.id == Trade.position_id)
        .join(Asset, Asset.id == Position.asset_id)
        .join(StrategyRow, StrategyRow.id == Position.strategy_id)
        .order_by(Trade.closed_at.desc())
        .limit(limit)
    ).all()
    return [
        TradeOut(
            id=trade.id, position_id=position.id, asset_symbol=asset.symbol, strategy_code=strategy.code,
            direction=position.direction, pnl=trade.pnl, r_multiple=trade.r_multiple, outcome=trade.outcome,
            is_paper=trade.is_paper, closed_at=trade.closed_at,
        )
        for trade, position, asset, strategy in rows
    ]


@router.get("/api/trades/{trade_id}/why", response_model=TradeWhyOut)
def get_trade_why(
    trade_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> TradeWhyOut:
    row = db.execute(
        select(Trade, Position, Asset, StrategyRow)
        .join(Position, Position.id == Trade.position_id)
        .join(Asset, Asset.id == Position.asset_id)
        .join(StrategyRow, StrategyRow.id == Position.strategy_id)
        .where(Trade.id == trade_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    trade, position, asset, strategy = row

    trade_out = TradeOut(
        id=trade.id, position_id=position.id, asset_symbol=asset.symbol, strategy_code=strategy.code,
        direction=position.direction, pnl=trade.pnl, r_multiple=trade.r_multiple, outcome=trade.outcome,
        is_paper=trade.is_paper, closed_at=trade.closed_at,
    )
    position_out = _position_out(db, position, asset, strategy)

    opportunity_out = None
    risk_decision_out = None
    if position.signal_id is not None:
        signal = db.get(Signal, position.signal_id)
        score = db.query(OpportunityScore).filter(OpportunityScore.signal_id == position.signal_id).first()
        regime = db.get(MarketRegime, signal.regime_id) if signal and signal.regime_id else None
        if signal and score and regime:
            risk = abs(signal.entry_price - signal.stop_price)
            reward = abs(signal.target_price - signal.entry_price) if signal.target_price is not None else 0.0
            opportunity_out = OpportunityDetailOut(
                signal_id=signal.id, asset_symbol=asset.symbol, strategy_code=strategy.code, strategy_name=strategy.name,
                direction=signal.direction, entry_price=signal.entry_price, stop_price=signal.stop_price,
                target_price=signal.target_price, risk_reward=(reward / risk if risk else 0.0),
                regime=regime.regime, regime_confidence=regime.confidence, status=signal.status, ts=signal.ts,
                score=ScoreBreakdown(
                    technical=score.technical, pattern=score.pattern, regime_fit=score.regime_fit,
                    historical_edge=score.historical_edge, liquidity=score.liquidity, news=score.news,
                    risk_reward=score.risk_reward, strategy_performance=score.strategy_performance,
                    volatility_penalty=score.volatility_penalty, correlation_penalty=score.correlation_penalty,
                    execution_cost_penalty=score.execution_cost_penalty, drawdown_penalty=score.drawdown_penalty,
                    final_score=score.final_score, tier=score.tier, notes=score.notes,
                ),
            )

        decision = db.query(RiskDecision).filter(RiskDecision.signal_id == position.signal_id).first()
        if decision:
            checks = db.query(RiskCheck).filter(RiskCheck.signal_id == position.signal_id).order_by(RiskCheck.id).all()
            risk_decision_out = RiskDecisionOut(
                signal_id=decision.signal_id, asset_symbol=asset.symbol, strategy_code=strategy.code,
                approved=decision.approved, approved_size=decision.approved_size, reason=decision.reason,
                safety_belt_level=decision.safety_belt_level, created_at=decision.created_at,
                checks=[RiskCheckOut(check_name=c.check_name, passed=c.passed, detail=c.detail) for c in checks],
            )

    return TradeWhyOut(trade=trade_out, position=position_out, opportunity=opportunity_out, risk_decision=risk_decision_out)
