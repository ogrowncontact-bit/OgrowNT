from datetime import datetime, timedelta, timezone

from apps.worker.news_agent import run_news_cycle
from packages.data.connectors.news.base import NewsItem
from packages.llm.client import LLMClient
from packages.shared.models import Asset, NewsEvent, NewsImpact


class _FixedNewsProvider:
    name = "fixed"

    def __init__(self, items):
        self._items = items

    def is_connected(self):
        return True

    def get_recent_news(self, since, limit=50):
        return [i for i in self._items if i.published_at >= since][:limit]


class _FakeLLMClient(LLMClient):
    def __init__(self, response):
        self._response = response

    def is_available(self):
        return True

    def complete_json(self, system_prompt, user_content, max_tokens=1024):
        return self._response


class _UnavailableLLMClient(LLMClient):
    def __init__(self):
        pass

    def is_available(self):
        return False


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    return asset


def test_ingests_items_without_interpretation_when_llm_unavailable(db_session):
    _asset(db_session, "NEWSAGENT1")
    item = NewsItem(source="Reuters", published_at=datetime.now(timezone.utc), headline="Some headline", body=None, raw_url=None, category="crypto")
    provider = _FixedNewsProvider([item])

    summary = run_news_cycle(db_session, provider, _UnavailableLLMClient())

    assert summary["ingested"] == 1
    assert summary["interpreted"] == 0
    assert summary["llm_available"] is False
    assert db_session.query(NewsEvent).filter(NewsEvent.headline == "Some headline").count() == 1
    assert db_session.query(NewsImpact).count() == 0


def test_ingests_and_interprets_when_llm_available(db_session):
    asset = _asset(db_session, "NEWSAGENT2")
    item = NewsItem(source="Reuters", published_at=datetime.now(timezone.utc), headline="Bullish headline", body=None, raw_url=None, category="crypto")
    provider = _FixedNewsProvider([item])
    llm = _FakeLLMClient([
        {"asset_symbol": "NEWSAGENT2", "direction": "bullish", "impact": "high", "confidence": 0.8, "horizon_hours": 12, "rationale": "ok"}
    ])

    summary = run_news_cycle(db_session, provider, llm)

    assert summary["ingested"] == 1
    assert summary["interpreted"] == 1
    impact = db_session.query(NewsImpact).filter(NewsImpact.asset_id == asset.id).first()
    assert impact is not None
    assert impact.direction == "bullish"


def test_watermark_prevents_reingesting_old_items(db_session):
    _asset(db_session, "NEWSAGENT3")
    old_item = NewsItem(source="Reuters", published_at=datetime.now(timezone.utc) - timedelta(hours=100), headline="Old news", body=None, raw_url=None, category="crypto")
    provider = _FixedNewsProvider([old_item])

    # Seed a watermark newer than old_item by ingesting a recent item first.
    recent_item = NewsItem(source="Reuters", published_at=datetime.now(timezone.utc), headline="Recent news", body=None, raw_url=None, category="crypto")
    run_news_cycle(db_session, _FixedNewsProvider([recent_item]), _UnavailableLLMClient())

    summary = run_news_cycle(db_session, provider, _UnavailableLLMClient())
    assert summary["ingested"] == 0  # old_item is before the new watermark


def test_no_new_items_is_a_clean_noop(db_session):
    _asset(db_session, "NEWSAGENT4")
    summary = run_news_cycle(db_session, _FixedNewsProvider([]), _UnavailableLLMClient())
    assert summary == {"ingested": 0, "interpreted": 0, "llm_available": False}
