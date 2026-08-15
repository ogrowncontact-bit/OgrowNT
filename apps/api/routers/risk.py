from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import RiskCheckOut, RiskDecisionOut, RiskStateOut
from packages.risk.config import load_risk_limits
from packages.shared.models import AdminUser, Asset, RiskCheck, RiskDecision, Signal, StrategyRow, SystemState

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("", response_model=RiskStateOut)
def get_risk_state(
    limit: int = 20, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> RiskStateOut:
    system_state = db.get(SystemState, True)
    limits = load_risk_limits()

    rows = db.execute(
        select(RiskDecision, Signal, Asset, StrategyRow)
        .join(Signal, Signal.id == RiskDecision.signal_id)
        .join(Asset, Asset.id == Signal.asset_id)
        .join(StrategyRow, StrategyRow.id == Signal.strategy_id)
        .order_by(RiskDecision.created_at.desc())
        .limit(limit)
    ).all()

    decisions = []
    for decision, signal, asset, strategy in rows:
        checks = db.query(RiskCheck).filter(RiskCheck.signal_id == signal.id).order_by(RiskCheck.id).all()
        decisions.append(
            RiskDecisionOut(
                signal_id=signal.id, asset_symbol=asset.symbol, strategy_code=strategy.code,
                approved=decision.approved, approved_size=decision.approved_size, reason=decision.reason,
                safety_belt_level=decision.safety_belt_level, created_at=decision.created_at,
                checks=[RiskCheckOut(check_name=c.check_name, passed=c.passed, detail=c.detail) for c in checks],
            )
        )

    return RiskStateOut(
        safety_belt_level=system_state.safety_belt_level if system_state else "normal",
        trading_enabled=system_state.trading_enabled if system_state else True,
        limits={
            "capital": asdict(limits.capital),
            "per_trade": asdict(limits.per_trade),
            "portfolio": asdict(limits.portfolio),
            "loss_limits": asdict(limits.loss_limits),
            "liquidity": asdict(limits.liquidity),
            "data_quality": asdict(limits.data_quality),
        },
        recent_decisions=decisions,
    )
