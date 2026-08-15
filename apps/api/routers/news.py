from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_session
from apps.api.schemas import NewsEventOut, NewsImpactOut
from packages.shared.models import Asset, NewsEvent, NewsImpact

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=list[NewsEventOut])
def list_news(limit: int = 50, db: Session = Depends(get_session)) -> list[NewsEventOut]:
    events = db.execute(select(NewsEvent).order_by(NewsEvent.published_at.desc()).limit(limit)).scalars().all()

    out = []
    for event in events:
        impacts = db.execute(
            select(NewsImpact, Asset).join(Asset, Asset.id == NewsImpact.asset_id).where(NewsImpact.news_event_id == event.id)
        ).all()
        out.append(
            NewsEventOut(
                id=event.id, source=event.source, published_at=event.published_at,
                headline=event.headline, category=event.category,
                impacts=[
                    NewsImpactOut(
                        asset_symbol=asset.symbol, direction=impact.direction, impact=impact.impact,
                        confidence=impact.confidence, horizon_hours=impact.horizon_hours, rationale=impact.rationale,
                    )
                    for impact, asset in impacts
                ],
            )
        )
    return out
