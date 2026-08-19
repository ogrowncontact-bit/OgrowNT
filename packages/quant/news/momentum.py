"""News Momentum — Prompt 6 §21: how much, how fast, how important, and how
concentrated (by source) recent news for one asset has been.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.shared.models import NewsEvent, NewsImpact

LOW, MEDIUM, HIGH = "low", "medium", "high"


@dataclass(frozen=True)
class NewsMomentum:
    asset_id: int
    count_lookback: int
    count_recent: int
    high_importance_count: int
    distinct_sources: int
    sentiment_mix: dict = field(default_factory=dict)  # {"bullish": n, ...}
    level: str = LOW


def compute_news_momentum(db: Session, asset_id: int, *, lookback_hours: float = 24.0) -> NewsMomentum:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)
    recent_cutoff = now - timedelta(hours=lookback_hours / 4)

    rows = db.execute(
        select(NewsEvent.importance, NewsEvent.sentiment, NewsEvent.source, NewsEvent.published_at)
        .join(NewsImpact, NewsImpact.news_event_id == NewsEvent.id)
        .where(NewsImpact.asset_id == asset_id, NewsEvent.published_at >= cutoff)
    ).all()

    count_lookback = len(rows)
    count_recent = sum(1 for r in rows if r.published_at >= recent_cutoff)
    high_importance = sum(1 for r in rows if r.importance in ("high", "critical"))
    distinct_sources = len({r.source for r in rows})
    sentiment_mix: dict[str, int] = {}
    for r in rows:
        sentiment_mix[r.sentiment] = sentiment_mix.get(r.sentiment, 0) + 1

    # Velocity: share of the window's items landing in its most recent
    # quarter. If news is accelerating, that share noticeably exceeds 25%.
    velocity_ratio = (count_recent / count_lookback) if count_lookback else 0.0

    if count_lookback >= 6 or high_importance >= 2 or velocity_ratio > 0.5:
        level = HIGH
    elif count_lookback >= 2 or high_importance >= 1:
        level = MEDIUM
    else:
        level = LOW

    return NewsMomentum(
        asset_id=asset_id, count_lookback=count_lookback, count_recent=count_recent,
        high_importance_count=high_importance, distinct_sources=distinct_sources,
        sentiment_mix=sentiment_mix, level=level,
    )
