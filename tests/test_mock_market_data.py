from packages.data.connectors.market.base import Candle
from packages.data.connectors.market.mock import MockMarketDataProvider


def test_mock_provider_returns_a_sane_candle():
    provider = MockMarketDataProvider()
    assert provider.is_connected()

    candle = provider.get_latest_candle("BTCUSDT", "1m")
    assert isinstance(candle, Candle)
    assert candle.data_quality == "high"
    assert candle.low <= candle.open <= candle.high
    assert candle.low <= candle.close <= candle.high
    assert candle.volume >= 0


def test_mock_provider_is_deterministic_within_the_same_minute():
    provider = MockMarketDataProvider()
    c1 = provider.get_latest_candle("EURUSD", "1m")
    c2 = provider.get_latest_candle("EURUSD", "1m")
    assert c1.close == c2.close  # same symbol/timeframe/minute -> same seed


def test_mock_provider_prices_differ_by_asset_class():
    provider = MockMarketDataProvider()
    btc = provider.get_latest_candle("BTCUSDT", "1m")
    eurusd = provider.get_latest_candle("EURUSD", "1m")
    # crypto base price (~30000) should be orders of magnitude above forex (~1.10)
    assert btc.close > eurusd.close * 100
