from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_session
from apps.api.schemas import PatternOut, PatternPerformanceOut
from packages.shared.models import Asset, Pattern, PatternPerformance

router = APIRouter(prefix="/api/patterns", tags=["patterns"])


@router.get("", response_model=list[PatternOut])
def list_patterns(asset_id: int | None = None, limit: int = 100, db: Session = Depends(get_session)) -> list[PatternOut]:
    query = select(Pattern, Asset).join(Asset, Asset.id == Pattern.asset_id)
    if asset_id is not None:
        query = query.where(Pattern.asset_id == asset_id)
    rows = db.execute(query.order_by(Pattern.ts.desc()).limit(limit)).all()

    return [
        PatternOut(
            id=pattern.id, asset_symbol=asset.symbol, timeframe=pattern.timeframe, ts=pattern.ts,
            pattern_type=pattern.pattern_type, pattern_class=pattern.pattern_class,
            direction=pattern.direction, strength=pattern.strength,
        )
        for pattern, asset in rows
    ]


@router.get("/performance", response_model=list[PatternPerformanceOut])
def list_pattern_performance(db: Session = Depends(get_session)) -> list[PatternPerformance]:
    return (
        db.execute(select(PatternPerformance).order_by(PatternPerformance.sample_size.desc()))
        .scalars()
        .all()
    )
