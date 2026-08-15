from datetime import datetime, timezone

from packages.data.connectors.news.base import NewsItem
from packages.llm.client import LLMClient
from packages.llm.news_intelligence import interpret_news_item


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


def _item(headline="Test headline") -> NewsItem:
    return NewsItem(source="Reuters", published_at=datetime.now(timezone.utc), headline=headline, body=None, raw_url=None, category="crypto")


def test_skips_interpretation_when_llm_unavailable():
    results = interpret_news_item(_UnavailableLLMClient(), _item(), ["BTCUSDT"])
    assert results == []


def test_accepts_well_formed_entry():
    client = _FakeLLMClient([
        {"asset_symbol": "BTCUSDT", "direction": "bullish", "impact": "high", "confidence": 0.7, "horizon_hours": 12, "rationale": "ok"}
    ])
    results = interpret_news_item(client, _item(), ["BTCUSDT", "ETHUSDT"])
    assert len(results) == 1
    assert results[0].asset_symbol == "BTCUSDT"
    assert results[0].direction == "bullish"


def test_drops_out_of_universe_symbol():
    client = _FakeLLMClient([
        {"asset_symbol": "TSLA", "direction": "bullish", "impact": "high", "confidence": 0.7, "horizon_hours": 12, "rationale": "ok"}
    ])
    assert interpret_news_item(client, _item(), ["BTCUSDT"]) == []


def test_drops_invalid_direction_and_impact_enums():
    client = _FakeLLMClient([
        {"asset_symbol": "BTCUSDT", "direction": "very bullish", "impact": "high", "confidence": 0.7, "horizon_hours": 12, "rationale": "x"},
        {"asset_symbol": "BTCUSDT", "direction": "bullish", "impact": "extreme", "confidence": 0.7, "horizon_hours": 12, "rationale": "x"},
    ])
    assert interpret_news_item(client, _item(), ["BTCUSDT"]) == []


def test_drops_out_of_range_confidence():
    client = _FakeLLMClient([
        {"asset_symbol": "BTCUSDT", "direction": "bullish", "impact": "high", "confidence": 1.5, "horizon_hours": 12, "rationale": "x"}
    ])
    assert interpret_news_item(client, _item(), ["BTCUSDT"]) == []


def test_drops_malformed_entry_missing_fields():
    client = _FakeLLMClient([{"asset_symbol": "BTCUSDT"}])
    assert interpret_news_item(client, _item(), ["BTCUSDT"]) == []


def test_non_list_response_is_discarded():
    client = _FakeLLMClient({"not": "a list"})
    assert interpret_news_item(client, _item(), ["BTCUSDT"]) == []


def test_empty_asset_universe_skips_call_entirely():
    results = interpret_news_item(_FakeLLMClient([{"asset_symbol": "X"}]), _item(), [])
    assert results == []
