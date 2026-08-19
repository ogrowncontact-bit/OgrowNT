from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import (
    AssetNewsContextOut,
    MacroEventOut,
    NewsEventOut,
    NewsImpactOut,
    NewsMomentumOut,
    NewsRiskOut,
    RecentNewsItemOut,
    SentimentShiftOut,
)
from packages.quant.news.context import build_asset_news_context
from packages.risk.config import load_risk_limits
from packages.risk.news_guard import evaluate_news_risk
from packages.shared.models import AdminUser, Asset, MacroEvent, NewsEvent, NewsImpact

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=list[NewsEventOut])
def list_news(
    limit: int = 50, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[NewsEventOut]:
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
                        is_direct=impact.is_direct,
                    )
                    for impact, asset in impacts
                ],
                source_quality_score=event.source_quality_score, sentiment=event.sentiment,
                sentiment_confidence=event.sentiment_confidence, importance=event.importance,
                novelty_score=event.novelty_score, impact_score=event.impact_score,
                cluster_id=event.cluster_id, source_consensus_score=event.source_consensus_score,
                has_conflicting_sources=event.has_conflicting_sources, entities=event.entities,
            )
        )
    return out


@router.get("/risk", response_model=NewsRiskOut)
def get_news_risk(db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)) -> NewsRiskOut:
    """Prompt 6 §26: current News Risk Guard level — the same check
    packages/risk/engine.py consults on every signal, computed live here for
    the dashboard's Event Risk panel."""
    verdict = evaluate_news_risk(db, load_risk_limits())
    return NewsRiskOut(
        level=verdict.level, size_multiplier=verdict.size_multiplier,
        blocked=verdict.blocked, reasons=verdict.reasons,
    )


@router.get("/context/{symbol}", response_model=AssetNewsContextOut)
def get_asset_news_context(
    symbol: str, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> AssetNewsContextOut:
    """Prompt 6 §20/§34: per-asset News + Sentiment + Event Risk + Momentum
    view for the dashboard's asset detail panel."""
    asset = db.query(Asset).filter(Asset.symbol == symbol.upper()).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown asset symbol: {symbol}")

    ctx = build_asset_news_context(db, asset.id)
    if ctx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown asset symbol: {symbol}")

    return AssetNewsContextOut(
        asset_id=ctx.asset_id, asset_symbol=ctx.asset_symbol,
        recent_news=[
            RecentNewsItemOut(
                news_event_id=n.news_event_id, headline=n.headline, source=n.source,
                published_at=n.published_at, sentiment=n.sentiment, importance=n.importance,
                direction=n.direction, impact=n.impact, confidence=n.confidence, is_direct=n.is_direct,
            )
            for n in ctx.recent_news
        ],
        momentum=NewsMomentumOut(
            count_lookback=ctx.momentum.count_lookback, count_recent=ctx.momentum.count_recent,
            high_importance_count=ctx.momentum.high_importance_count, distinct_sources=ctx.momentum.distinct_sources,
            sentiment_mix=ctx.momentum.sentiment_mix, level=ctx.momentum.level,
        ) if ctx.momentum else None,
        sentiment_shift=SentimentShiftOut(
            recent_bullish_share=ctx.sentiment_shift.recent_bullish_share,
            baseline_bullish_share=ctx.sentiment_shift.baseline_bullish_share,
            recent_count=ctx.sentiment_shift.recent_count, baseline_count=ctx.sentiment_shift.baseline_count,
            shift=ctx.sentiment_shift.shift, detected=ctx.sentiment_shift.detected,
        ) if ctx.sentiment_shift else None,
        avg_source_quality=ctx.avg_source_quality,
    )


macro_router = APIRouter(prefix="/api/macro", tags=["news"])


@macro_router.get("", response_model=list[MacroEventOut])
def list_macro_events(
    days_back: int = 3, days_ahead: int = 14,
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin),
) -> list[MacroEventOut]:
    """Prompt 6 §35: the macro economic calendar."""
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(MacroEvent)
        .where(
            MacroEvent.scheduled_at >= now - timedelta(days=days_back),
            MacroEvent.scheduled_at <= now + timedelta(days=days_ahead),
        )
        .order_by(MacroEvent.scheduled_at.asc())
    ).scalars().all()
    return [
        MacroEventOut(
            id=r.id, event=r.event, country=r.country, currency=r.currency, scheduled_at=r.scheduled_at,
            importance=r.importance, forecast=r.forecast, previous=r.previous, actual=r.actual,
            surprise=r.surprise, status=r.status,
        )
        for r in rows
    ]
