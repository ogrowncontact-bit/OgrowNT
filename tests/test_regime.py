from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.quant.regime.classifier import (
    REGIME_LOW_VOLATILITY,
    REGIME_TRENDING_BEAR,
    REGIME_TRENDING_BULL,
    REGIME_UNKNOWN,
    classify_regime,
)


def _trend(n=60, step=0.6) -> list[Candle]:
    ts = datetime.now(timezone.utc) - timedelta(minutes=n)
    price = 100.0
    candles = []
    for i in range(n):
        price += step
        candles.append(
            Candle(ts=ts + timedelta(minutes=i), open=price - 0.1, high=price + 0.2, low=price - 0.2, close=price, volume=100)
        )
    return candles


def _flat(n=60) -> list[Candle]:
    ts = datetime.now(timezone.utc) - timedelta(minutes=n)
    return [
        Candle(ts=ts + timedelta(minutes=i), open=100.0, high=100.02, low=99.98, close=100.0, volume=100)
        for i in range(n)
    ]


def test_uptrend_classified_as_trending_bull():
    result = classify_regime(_trend(step=0.6))
    assert result.regime == REGIME_TRENDING_BULL
    assert result.confidence > 0


def test_downtrend_classified_as_trending_bear():
    result = classify_regime(_trend(step=-0.6))
    assert result.regime == REGIME_TRENDING_BEAR


def test_flat_series_classified_as_low_volatility():
    result = classify_regime(_flat())
    assert result.regime == REGIME_LOW_VOLATILITY


def test_insufficient_history_is_unknown():
    result = classify_regime(_trend(n=10))
    assert result.regime == REGIME_UNKNOWN
    assert result.confidence == 0.0
