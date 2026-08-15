from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_session
from apps.api.schemas import PortfolioResponse, PortfolioSnapshotOut
from packages.shared.models import PortfolioSnapshot

router = APIRouter(tags=["portfolio"])


@router.get("/api/portfolio", response_model=PortfolioResponse)
def get_portfolio(db: Session = Depends(get_session)) -> PortfolioResponse:
    latest = db.execute(
        select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(1)
    ).scalar_one_or_none()
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No portfolio snapshot yet — run scripts/seed.py",
        )
    return PortfolioResponse(
        equity=latest.equity,
        cash=latest.cash,
        exposure_pct=latest.exposure_pct,
        daily_pnl=latest.daily_pnl,
        drawdown_pct=latest.drawdown_pct,
        safety_belt_level=latest.safety_belt_level,
        as_of=latest.ts,
    )


@router.get("/api/portfolio/history", response_model=list[PortfolioSnapshotOut])
def get_portfolio_history(limit: int = 500, db: Session = Depends(get_session)) -> list[PortfolioSnapshot]:
    return (
        db.execute(select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(limit))
        .scalars()
        .all()
    )


