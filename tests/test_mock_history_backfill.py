from packages.data.connectors.market.mock import MockMarketDataProvider


def test_get_recent_candles_returns_requested_count_chronological():
    provider = MockMarketDataProvider()
    candles = provider.get_recent_candles("BTCUSDT", "1m", 60)
    assert len(candles) == 60
    assert candles[0].ts < candles[-1].ts
    assert all(c.low <= c.close <= c.high for c in candles)


def test_get_recent_candles_is_deterministic_per_symbol():
    provider = MockMarketDataProvider()
    a = provider.get_recent_candles("ETHUSDT", "1m", 30)
    b = provider.get_recent_candles("ETHUSDT", "1m", 30)
    assert [c.close for c in a] == [c.close for c in b]


def test_get_recent_candles_caps_at_500():
    provider = MockMarketDataProvider()
    candles = provider.get_recent_candles("EURUSD", "1m", 10_000)
    assert len(candles) == 500
