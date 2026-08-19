from datetime import datetime, timedelta, timezone

from apps.worker.news_agent import run_news_cycle
from packages.data.connectors.news.base import NewsItem
from packages.llm.client import LLMClient
from packages.shared.models import Alert, Asset, NewsEvent

NOW = datetime.now(timezone.utc)


class _FakeNewsProvider:
    name = "fake"

    def __init__(self, items: list[NewsItem]) -> None:
        self._items = items

    def is_connected(self) -> bool:
        return True

    def get_recent_news(self, since, limit: int = 50) -> list[NewsItem]:
        return [i for i in self._items if i.published_at >= since][:limit]


def _item(headline: str, *, source: str = "Reuters", category: str = "central_bank", minutes_ago: float = 1.0) -> NewsItem:
    return NewsItem(
        source=source, published_at=NOW - timedelta(minutes=minutes_ago), headline=headline,
        body=None, raw_url=None, category=category,
    )


def test_ingested_event_gets_full_det_analysis(db_session):
    llm = LLMClient()  # no ANTHROPIC_API_KEY in test env -- interpretation stays honestly skipped
    provider = _FakeNewsProvider([_item("Central bank holds policy rate steady")])

    summary = run_news_cycle(db_session, provider, llm)
    assert summary["ingested"] == 1

    event = db_session.query(NewsEvent).filter(NewsEvent.headline == "Central bank holds policy rate steady").first()
    assert event is not None
    assert event.source_quality_score == 95.0  # Reuters is a known wire service
    assert event.importance in ("low", "medium", "high", "critical")
    assert event.cluster_id == event.id  # first item in its story -- canonical cluster
    assert event.novelty_score == 100.0


def test_second_similar_headline_joins_the_first_items_cluster(db_session):
    llm = LLMClient()
    provider = _FakeNewsProvider([
        _item("Central bank holds rates", source="Reuters", minutes_ago=10),
        _item("Central bank keeps policy unchanged", source="Bloomberg", minutes_ago=1),
    ])
    run_news_cycle(db_session, provider, llm)

    first = db_session.query(NewsEvent).filter(NewsEvent.headline == "Central bank holds rates").first()
    second = db_session.query(NewsEvent).filter(NewsEvent.headline == "Central bank keeps policy unchanged").first()
    assert first.cluster_id == second.cluster_id
    # The second item is a repeat of the same story -- lower novelty than a
    # brand-new one, and consensus should reflect a second independent source.
    assert second.novelty_score < first.novelty_score
    assert second.source_consensus_score > 0


def test_critical_news_raises_an_alert(db_session):
    llm = LLMClient()
    provider = _FakeNewsProvider([_item("Major bank collapse triggers emergency crisis talks", category="banking")])
    run_news_cycle(db_session, provider, llm)

    alert = db_session.query(Alert).filter(Alert.category == "news").filter(
        Alert.message.like("%Critical news%bank collapse%")
    ).first()
    assert alert is not None
    assert alert.severity == "critical"


def test_asset_universe_used_for_direct_mapping(db_session):
    asset = Asset(symbol="AAPL", asset_class="equity", is_active=True)
    db_session.add(asset)
    db_session.commit()

    llm = LLMClient()
    provider = _FakeNewsProvider([_item("Apple supplier warns about chip shortages", category="supply_chain")])
    run_news_cycle(db_session, provider, llm)

    event = db_session.query(NewsEvent).filter(NewsEvent.headline.like("Apple supplier%")).first()
    assert event is not None
    # AAPL is named directly -> impact_score should reflect direct relevance
    # even though there was no LLM interpretation (no ANTHROPIC_API_KEY set).
    assert event.impact_score > 0
