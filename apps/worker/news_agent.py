"""News Intelligence Agent cycle — docs/blueprint/04-agents-architecture.md#agent-03,
docs/news-intelligence.md.

Ingestion plus the full DET analysis pipeline (Prompt 6 §4-14, §23-24):
source quality, deduplication/clustering, novelty, entity extraction, asset
mapping (direct vs indirect), sentiment (the headline/body's own tone,
independent of the LLM's direction call), importance, impact score. Every
one of those is deterministic (packages/quant/news) — this module calls
the LLM (packages/llm/news_intelligence.py) for exactly one thing: the
per-asset direction/impact/confidence/rationale read, same as before
Prompt 6. If no ANTHROPIC_API_KEY is set, ingestion + DET analysis still
runs (news_events fills up with real sentiment/importance/impact_score)
but that one interpretation step is skipped — logged, not faked.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.data.connectors.news.base import NewsItem, NewsProvider
from packages.llm.client import LLMClient
from packages.llm.news_intelligence import interpret_news_item
from packages.quant.news.asset_mapping import AssetMapping, map_entities_to_assets
from packages.quant.news.dedup import DEFAULT_CLUSTER_WINDOW_HOURS, ClusterCandidate, compute_source_consensus, find_cluster
from packages.quant.news.entities import extract_entities
from packages.quant.news.impact_score import compute_impact_score
from packages.quant.news.importance import classify_importance
from packages.quant.news.novelty import compute_novelty_score
from packages.quant.news.sentiment import classify_sentiment
from packages.quant.news.source_quality import score_source
from packages.shared.models import Alert, Asset, NewsEvent, NewsImpact

logger = logging.getLogger("worker.news_agent")

DEFAULT_LOOKBACK_HOURS = 24


def _watermark(db: Session) -> datetime:
    latest = db.query(NewsEvent).order_by(NewsEvent.published_at.desc()).first()
    if latest is not None:
        return latest.published_at
    return datetime.now(timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)


def _recent_cluster_candidates(db: Session, now: datetime) -> list[ClusterCandidate]:
    cutoff = now - timedelta(hours=DEFAULT_CLUSTER_WINDOW_HOURS)
    rows = db.query(NewsEvent).filter(NewsEvent.published_at >= cutoff).all()
    return [
        ClusterCandidate(
            news_event_id=r.id, cluster_id=r.cluster_id or r.id, headline=r.headline,
            category=r.category, source=r.source, sentiment=r.sentiment, published_at=r.published_at,
        )
        for r in rows
    ]


def _analyze_and_persist_news_event(
    db: Session, item: NewsItem, asset_universe: set[str]
) -> tuple[NewsEvent, list[AssetMapping]]:
    now = datetime.now(timezone.utc)
    sentiment_result = classify_sentiment(item.headline, item.body)
    importance = classify_importance(item.category, item.headline, item.body)
    source_quality = score_source(item.source)

    candidates = _recent_cluster_candidates(db, item.published_at)
    match = find_cluster(item.headline, item.category, candidates)
    consensus = compute_source_consensus([], item.source, sentiment_result.sentiment)
    prior_cluster_member_count = 0
    if match is not None:
        cluster_members = [c for c in candidates if c.cluster_id == match.cluster_id]
        prior_cluster_member_count = len(cluster_members)
        consensus = compute_source_consensus(cluster_members, item.source, sentiment_result.sentiment)

    novelty_score = compute_novelty_score(prior_cluster_member_count)

    entities = extract_entities(item.headline, item.body)
    asset_mappings = map_entities_to_assets(entities, asset_universe)
    is_direct_overall = any(m.is_direct for m in asset_mappings) if asset_mappings else False

    impact_score = compute_impact_score(
        source_quality_score=source_quality, importance=importance, is_direct=is_direct_overall,
        novelty_score=novelty_score, confidence=sentiment_result.confidence,
    )

    news_event = NewsEvent(
        source=item.source, published_at=item.published_at, headline=item.headline,
        body=item.body, raw_url=item.raw_url, category=item.category, retrieved_at=now,
        source_quality_score=source_quality,
        entities=[{"type": e.type, "value": e.value} for e in entities],
        novelty_score=novelty_score,
        source_consensus_score=consensus.consensus_score, has_conflicting_sources=consensus.has_conflict,
        sentiment=sentiment_result.sentiment, sentiment_confidence=sentiment_result.confidence,
        importance=importance, impact_score=impact_score,
    )
    db.add(news_event)
    db.flush()  # need news_event.id before it can point at itself/its cluster

    news_event.cluster_id = match.cluster_id if match is not None else news_event.id
    _raise_news_alerts(db, news_event)
    return news_event, asset_mappings


def _raise_news_alerts(db: Session, news_event: NewsEvent) -> None:
    """Prompt 6 §36: CRITICAL_NEWS and CONFLICTING_INFORMATION alerts, raised
    at the moment they're first known to be true for this item."""
    if news_event.importance == "critical":
        db.add(
            Alert(
                severity="critical", category="news",
                message=f"Critical news: {news_event.headline}",
                meta={"marker": "critical_news", "news_event_id": news_event.id, "source": news_event.source},
            )
        )
    if news_event.has_conflicting_sources:
        db.add(
            Alert(
                severity="warning", category="news",
                message=f"Conflicting reports on: {news_event.headline}",
                meta={"marker": "conflicting_information", "news_event_id": news_event.id},
            )
        )


def run_news_cycle(db: Session, provider: NewsProvider, llm_client: LLMClient) -> dict:
    since = _watermark(db)
    items = provider.get_recent_news(since=since)

    assets = db.query(Asset).filter(Asset.is_active.is_(True)).all()
    asset_symbols = [a.symbol for a in assets]
    asset_universe = set(asset_symbols)

    ingested, interpreted = 0, 0
    for item in items:
        news_event, asset_mappings = _analyze_and_persist_news_event(db, item, asset_universe)
        is_direct_by_symbol = {m.asset_symbol: m.is_direct for m in asset_mappings}
        ingested += 1

        results = interpret_news_item(llm_client, item, asset_symbols)
        if results:
            symbol_to_asset_id = {
                a.symbol: a.id for a in db.query(Asset).filter(Asset.symbol.in_([r.asset_symbol for r in results])).all()
            }
            for result in results:
                asset_id = symbol_to_asset_id.get(result.asset_symbol)
                if asset_id is None:
                    continue
                db.add(
                    NewsImpact(
                        news_event_id=news_event.id, asset_id=asset_id, impact=result.impact,
                        direction=result.direction, confidence=result.confidence,
                        horizon_hours=result.horizon_hours, rationale=result.rationale,
                        is_direct=is_direct_by_symbol.get(result.asset_symbol, True),
                    )
                )
                interpreted += 1

        logger.info(
            "News: %r (%s, importance=%s, sentiment=%s) — %d asset impact(s) interpreted",
            item.headline, item.category, news_event.importance, news_event.sentiment, len(results),
        )

    db.commit()
    summary = {"ingested": ingested, "interpreted": interpreted, "llm_available": llm_client.is_available()}
    logger.info("News cycle complete: %s", summary)
    return summary
