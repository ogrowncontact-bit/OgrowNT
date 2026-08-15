import random
from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.quant.regime.classifier import (
    REGIME_EUPHORIA,
    REGIME_HIGH_VOLATILITY,
    REGIME_PANIC,
    REGIME_TRANSITION,
    NewsSignal,
    classify_regime,
    classify_regime_with_news,
)


def _high_vol_no_trend_candles(n=60) -> list[Candle]:
    rng = random.Random(11)
    ts = datetime.now(timezone.utc) - timedelta(minutes=n)
    candles = []
    for i in range(n):
        price = 100.0 + 8.0 * ((i % 4) - 1.5) + rng.uniform(-1, 1)
        candles.append(Candle(ts=ts + timedelta(minutes=i), open=price, high=price * 1.02, low=price * 0.98, close=price, volume=100))
    return candles


def test_base_classification_is_high_volatility_with_no_news():
    candles = _high_vol_no_trend_candles()
    assert classify_regime(candles).regime == REGIME_HIGH_VOLATILITY
    assert classify_regime_with_news(candles, []).regime == REGIME_HIGH_VOLATILITY


def test_strong_bearish_news_reclassifies_as_panic():
    candles = _high_vol_no_trend_candles()
    news = [NewsSignal(direction="bearish", impact="high", confidence=0.8)]
    assert classify_regime_with_news(candles, news).regime == REGIME_PANIC


def test_strong_bullish_news_reclassifies_as_euphoria():
    candles = _high_vol_no_trend_candles()
    news = [NewsSignal(direction="bullish", impact="high", confidence=0.8)]
    assert classify_regime_with_news(candles, news).regime == REGIME_EUPHORIA


def test_mixed_direction_news_is_transition():
    candles = _high_vol_no_trend_candles()
    news = [
        NewsSignal(direction="bullish", impact="high", confidence=0.8),
        NewsSignal(direction="bearish", impact="high", confidence=0.75),
    ]
    assert classify_regime_with_news(candles, news).regime == REGIME_TRANSITION


def test_low_confidence_news_is_transition_not_panic():
    candles = _high_vol_no_trend_candles()
    news = [NewsSignal(direction="bearish", impact="medium", confidence=0.4)]
    assert classify_regime_with_news(candles, news).regime == REGIME_TRANSITION


def test_news_never_changes_a_non_high_volatility_regime():
    # A calm, low-volatility series shouldn't be reclassified by news at all
    # -- panic/euphoria/transition only ever override high_volatility.
    ts = datetime.now(timezone.utc) - timedelta(minutes=60)
    candles = [
        Candle(ts=ts + timedelta(minutes=i), open=100, high=100.01, low=99.99, close=100, volume=100) for i in range(60)
    ]
    base = classify_regime(candles)
    news = [NewsSignal(direction="bearish", impact="high", confidence=0.9)]
    with_news = classify_regime_with_news(candles, news)
    assert with_news.regime == base.regime
