"""Event-reaction research (`research_queue.queue_type == "event_test"`) —
"PROMPT 10" §22-24 applied to news/macro events instead of chart patterns.

Reads Prompt 6's own Event Reaction Memory (`EventReaction` — how a given
asset has historically reacted to a category of news/macro event) the same
way `packages.research.features` reads `PatternPerformance`: a
correlation-only lookup over evidence a different, already-built pipeline
computes, never a new event-impact compute engine.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.shared.models import EventReaction


def research_event_reaction(db: Session, *, event_category: str, asset_id: int) -> EventReaction | None:
    return (
        db.execute(
            select(EventReaction)
            .where(EventReaction.event_category == event_category, EventReaction.asset_id == asset_id)
            .order_by(EventReaction.as_of.desc())
        )
        .scalars()
        .first()
    )
