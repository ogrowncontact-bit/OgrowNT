from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import EvidenceItemOut, OpportunityDetailOut, OpportunityOut, RegimeOut, ScoreBreakdown
from packages.quant.scoring import build_evidence
from packages.shared.models import AdminUser, Asset, MarketRegime, OpportunityScore, Signal, StrategyRow

router = APIRouter(tags=["opportunities"])


def _risk_reward(signal: Signal) -> float:
    if signal.target_price is None or signal.entry_price == signal.stop_price:
        return 0.0
    return abs(signal.target_price - signal.entry_price) / abs(signal.entry_price - signal.stop_price)


@router.get("/api/opportunities", response_model=list[OpportunityOut])
def list_opportunities(
    limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[OpportunityOut]:
    rows = db.execute(
        select(Signal, Asset, StrategyRow, MarketRegime, OpportunityScore)
        .join(Asset, Asset.id == Signal.asset_id)
        .join(StrategyRow, StrategyRow.id == Signal.strategy_id)
        .join(MarketRegime, MarketRegime.id == Signal.regime_id)
        .join(OpportunityScore, OpportunityScore.signal_id == Signal.id)
        .where(OpportunityScore.tier != "ignore")
        .order_by(OpportunityScore.final_score.desc())
        .limit(limit)
    ).all()

    return [
        OpportunityOut(
            signal_id=signal.id,
            asset_symbol=asset.symbol,
            strategy_code=strategy.code,
            strategy_name=strategy.name,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_price=signal.stop_price,
            target_price=signal.target_price,
            risk_reward=_risk_reward(signal),
            regime=regime.regime,
            final_score=score.final_score,
            confidence=score.confidence,
            tier=score.tier,
            ts=signal.ts,
            opportunity_type=signal.opportunity_type,
            fingerprint=signal.fingerprint,
            expires_at=signal.expires_at,
        )
        for signal, asset, strategy, regime, score in rows
    ]


@router.get("/api/opportunities/{signal_id}", response_model=OpportunityDetailOut)
def get_opportunity(
    signal_id: int, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> OpportunityDetailOut:
    row = db.execute(
        select(Signal, Asset, StrategyRow, MarketRegime, OpportunityScore)
        .join(Asset, Asset.id == Signal.asset_id)
        .join(StrategyRow, StrategyRow.id == Signal.strategy_id)
        .join(MarketRegime, MarketRegime.id == Signal.regime_id)
        .join(OpportunityScore, OpportunityScore.signal_id == Signal.id)
        .where(Signal.id == signal_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")

    signal, asset, strategy, regime, score = row
    rr = _risk_reward(signal)

    evidence = build_evidence(
        direction=signal.direction, technical=score.technical, pattern=score.pattern,
        regime=regime.regime, regime_fit=score.regime_fit, regime_confidence=regime.confidence,
        historical_edge=score.historical_edge, liquidity=score.liquidity, news=score.news,
        risk_reward=score.risk_reward, risk_reward_ratio=rr,
        volatility_penalty=score.volatility_penalty, notes=score.notes,
    )

    return OpportunityDetailOut(
        signal_id=signal.id,
        asset_symbol=asset.symbol,
        strategy_code=strategy.code,
        strategy_name=strategy.name,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
        target_price=signal.target_price,
        risk_reward=rr,
        regime=regime.regime,
        regime_confidence=regime.confidence,
        status=signal.status,
        ts=signal.ts,
        score=ScoreBreakdown(
            technical=score.technical,
            pattern=score.pattern,
            regime_fit=score.regime_fit,
            historical_edge=score.historical_edge,
            liquidity=score.liquidity,
            news=score.news,
            risk_reward=score.risk_reward,
            strategy_performance=score.strategy_performance,
            volatility_penalty=score.volatility_penalty,
            correlation_penalty=score.correlation_penalty,
            execution_cost_penalty=score.execution_cost_penalty,
            drawdown_penalty=score.drawdown_penalty,
            final_score=score.final_score,
            confidence=score.confidence,
            tier=score.tier,
            notes=score.notes,
        ),
        evidence=[EvidenceItemOut(kind=e.kind, text=e.text) for e in evidence],
        opportunity_type=signal.opportunity_type,
        fingerprint=signal.fingerprint,
        expires_at=signal.expires_at,
    )


@router.get("/api/signals", response_model=list[OpportunityOut])
def list_signals(
    limit: int = 100, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[OpportunityOut]:
    """All signals regardless of tier (including 'ignore') — the full record
    of what the Strategy Engine considered, for audit/debugging. The
    dashboard's opportunity list uses /api/opportunities instead, which
    excludes 'ignore'.
    """
    rows = db.execute(
        select(Signal, Asset, StrategyRow, MarketRegime, OpportunityScore)
        .join(Asset, Asset.id == Signal.asset_id)
        .join(StrategyRow, StrategyRow.id == Signal.strategy_id)
        .join(MarketRegime, MarketRegime.id == Signal.regime_id)
        .join(OpportunityScore, OpportunityScore.signal_id == Signal.id)
        .order_by(Signal.ts.desc())
        .limit(limit)
    ).all()

    return [
        OpportunityOut(
            signal_id=signal.id,
            asset_symbol=asset.symbol,
            strategy_code=strategy.code,
            strategy_name=strategy.name,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_price=signal.stop_price,
            target_price=signal.target_price,
            risk_reward=_risk_reward(signal),
            regime=regime.regime,
            final_score=score.final_score,
            confidence=score.confidence,
            tier=score.tier,
            ts=signal.ts,
            opportunity_type=signal.opportunity_type,
            fingerprint=signal.fingerprint,
            expires_at=signal.expires_at,
        )
        for signal, asset, strategy, regime, score in rows
    ]


@router.get("/api/regime", response_model=list[RegimeOut])
def get_regime(
    asset_id: int | None = None, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[RegimeOut]:
    """Latest known regime per asset (docs/blueprint/04-agents-architecture.md#agent-06)."""
    query = select(MarketRegime, Asset).join(Asset, Asset.id == MarketRegime.asset_id)
    if asset_id is not None:
        query = query.where(MarketRegime.asset_id == asset_id)

    # Latest row per asset: order desc and keep the first occurrence per asset_id.
    rows = db.execute(query.order_by(MarketRegime.asset_id, MarketRegime.ts.desc())).all()
    latest_by_asset: dict[int, tuple] = {}
    for regime, asset in rows:
        latest_by_asset.setdefault(asset.id, (regime, asset))

    return [
        RegimeOut(
            asset_symbol=asset.symbol,
            timeframe=regime.timeframe,
            ts=regime.ts,
            regime=regime.regime,
            confidence=regime.confidence,
            features=regime.features,
        )
        for regime, asset in latest_by_asset.values()
    ]
