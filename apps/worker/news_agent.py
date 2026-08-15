"""News Intelligence Agent cycle — docs/blueprint/04-agents-architecture.md#agent-03.

Ingests real (or, in Phase 4 dev, mock-but-labeled) news items and, when an
LLM is configured, interprets them into news_impact rows. If no
ANTHROPIC_API_KEY is set, ingestion still runs (news_events fills up) but
interpretation is skipped — logged, not faked.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.data.connectors.news.base import NewsProvider
from packages.llm.client import LLMClient
from packages.llm.news_intelligence import interpret_news_item
from packages.shared.models import Asset, NewsEvent, NewsImpact

logger = logging.getLogger("worker.news_agent")

DEFAULT_LOOKBACK_HOURS = 24


def _watermark(db: Session) -> datetime:
    latest = db.query(NewsEvent).order_by(NewsEvent.published_at.desc()).first()
    if latest is not None:
        return latest.published_at
    return datetime.now(timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)


def run_news_cycle(db: Session, provider: NewsProvider, llm_client: LLMClient) -> dict:
    since = _watermark(db)
    items = provider.get_recent_news(since=since)

    asset_symbols = [a.symbol for a in db.query(Asset).filter(Asset.is_active.is_(True)).all()]

    ingested, interpreted = 0, 0
    for item in items:
        news_event = NewsEvent(
            source=item.source, published_at=item.published_at, headline=item.headline,
            body=item.body, raw_url=item.raw_url, category=item.category,
        )
        db.add(news_event)
        db.flush()
        ingested += 1

        results = interpret_news_item(llm_client, item, asset_symbols)
        if results:
            symbol_to_asset_id = {a.symbol: a.id for a in db.query(Asset).filter(Asset.symbol.in_([r.asset_symbol for r in results])).all()}
            for result in results:
                asset_id = symbol_to_asset_id.get(result.asset_symbol)
                if asset_id is None:
                    continue
                db.add(
                    NewsImpact(
                        news_event_id=news_event.id, asset_id=asset_id, impact=result.impact,
                        direction=result.direction, confidence=result.confidence,
                        horizon_hours=result.horizon_hours, rationale=result.rationale,
                    )
                )
                interpreted += 1

        logger.info(
            "News: %r (%s) — %d asset impact(s) interpreted", item.headline, item.category, len(results)
        )

    db.commit()
    summary = {"ingested": ingested, "interpreted": interpreted, "llm_available": llm_client.is_available()}
    logger.info("News cycle complete: %s", summary)
    return summary
