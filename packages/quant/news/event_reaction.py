"""Event Reaction Memory — Prompt 6 §19/§30-32.

"How does this category of event usually move this asset?" Recomputed
from real historical price moves following past news_events, the same
rolling-recompute pattern as StrategyPerformance
(packages/quant/learning/strategy_stats.py). `confidence` — not just
sample_size — is what gates whether a caller ever surfaces this ("só
mostrar estatísticas quando a amostra for suficiente", §19): below
MIN_SAMPLES_FOR_REACTION, a category/asset pair simply doesn't get a row
with real numbers, rather than showing a confident-looking stat built on
2 observations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.shared.market_data import get_close_at_or_after
from packages.shared.models import Asset, EventReaction, NewsEvent, NewsImpact

MIN_SAMPLES_FOR_REACTION = 5
DEFAULT_REACTION_HORIZON_HOURS = 4.0


def _reaction_pct(db: Session, asset_id: int, published_at, horizon_hours: float) -> float | None:
    before = get_close_at_or_after(db, asset_id, published_at)
    after = get_close_at_or_after(db, asset_id, published_at + timedelta(hours=horizon_hours))
    if before is None or after is None or before == 0:
        return None
    return (after - before) / before * 100.0


def compute_event_reactions(db: Session, *, horizon_hours: float = DEFAULT_REACTION_HORIZON_HOURS) -> int:
    """Recomputes every (event_category, asset) EventReaction row from
    completed observations (news old enough that `horizon_hours` has
    already elapsed since publication). Returns the number of rows
    written/updated."""
    assets = db.query(Asset).filter(Asset.is_active.is_(True)).all()
    written = 0

    for asset in assets:
        rows = (
            db.query(NewsEvent.category, NewsEvent.published_at)
            .join(NewsImpact, NewsImpact.news_event_id == NewsEvent.id)
            .filter(NewsImpact.asset_id == asset.id, NewsEvent.category.isnot(None))
            .all()
        )
        by_category: dict[str, list] = {}
        for category, published_at in rows:
            by_category.setdefault(category, []).append(published_at)

        for category, published_ats in by_category.items():
            reactions = [
                r for r in (_reaction_pct(db, asset.id, ts, horizon_hours) for ts in published_ats) if r is not None
            ]
            if len(reactions) < MIN_SAMPLES_FOR_REACTION:
                continue

            existing = (
                db.query(EventReaction)
                .filter(EventReaction.event_category == category, EventReaction.asset_id == asset.id)
                .first()
            )
            avg_reaction = sum(reactions) / len(reactions)
            positive_rate = sum(1 for r in reactions if r > 0) / len(reactions)
            confidence = round(min(1.0, len(reactions) / 20.0), 4)

            if existing is None:
                existing = EventReaction(event_category=category, asset_id=asset.id)
                db.add(existing)
            existing.sample_size = len(reactions)
            existing.avg_reaction_pct = round(avg_reaction, 4)
            existing.positive_rate = round(positive_rate, 4)
            existing.confidence = confidence
            existing.as_of = datetime.now(timezone.utc)
            written += 1

    db.commit()
    return written
