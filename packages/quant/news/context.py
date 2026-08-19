"""NewsContextEngine — Prompt 6 §20/§34: the per-asset aggregate view
(recent news, sentiment shift, momentum, source quality) the Opportunity
Engine, Risk Engine, and dashboard all read from. Pure aggregation over
already-computed data — never a decision itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.quant.news.momentum import NewsMomentum, compute_news_momentum
from packages.quant.news.sentiment import SentimentShift, compute_sentiment_shift
from packages.shared.models import Asset, NewsEvent, NewsImpact


@dataclass(frozen=True)
class RecentNewsItem:
    news_event_id: int
    headline: str
    source: str
    published_at: datetime
    sentiment: str
    importance: str
    direction: str
    impact: str
    confidence: float
    is_direct: bool


@dataclass(frozen=True)
class AssetNewsContext:
    asset_id: int
    asset_symbol: str
    recent_news: list[RecentNewsItem] = field(default_factory=list)
    momentum: NewsMomentum | None = None
    sentiment_shift: SentimentShift | None = None
    avg_source_quality: float | None = None


def build_asset_news_context(
    db: Session, asset_id: int, *, lookback_hours: float = 48.0, limit: int = 10
) -> AssetNewsContext | None:
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    rows = db.execute(
        select(NewsEvent, NewsImpact)
        .join(NewsImpact, NewsImpact.news_event_id == NewsEvent.id)
        .where(NewsImpact.asset_id == asset_id, NewsEvent.published_at >= cutoff)
        .order_by(NewsEvent.published_at.desc())
        .limit(limit)
    ).all()

    recent_news = [
        RecentNewsItem(
            news_event_id=event.id, headline=event.headline, source=event.source,
            published_at=event.published_at, sentiment=event.sentiment, importance=event.importance,
            direction=impact.direction, impact=impact.impact, confidence=impact.confidence,
            is_direct=impact.is_direct,
        )
        for event, impact in rows
    ]
    quality_scores = [event.source_quality_score for event, _ in rows]
    avg_quality = round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else None

    return AssetNewsContext(
        asset_id=asset_id, asset_symbol=asset.symbol, recent_news=recent_news,
        momentum=compute_news_momentum(db, asset_id),
        sentiment_shift=compute_sentiment_shift(db, asset_id),
        avg_source_quality=avg_quality,
    )
