from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import (
    atr,
    compute_indicators,
    ema,
    realized_volatility,
    rsi,
    sma,
    trend_strength,
)


def _candles(closes: list[float]) -> list[Candle]:
    ts = datetime.now(timezone.utc)
    return [
        Candle(ts=ts + timedelta(minutes=i), open=c, high=c + 0.5, low=c - 0.5, close=c, volume=100)
        for i, c in enumerate(closes)
    ]


def test_sma_and_ema_basic():
    closes = [float(i) for i in range(1, 11)]  # 1..10
    assert sma(closes, 5) == sum(closes[-5:]) / 5
    assert sma(closes, 20) is None  # not enough data
    assert ema(closes, 5) is not None


def test_rsi_all_gains_is_100():
    closes = [float(i) for i in range(1, 20)]  # strictly increasing
    assert rsi(closes, 14) == 100.0


def test_rsi_all_losses_is_0():
    closes = [float(i) for i in range(20, 1, -1)]  # strictly decreasing
    assert rsi(closes, 14) == 0.0


def test_atr_requires_period_plus_one_candles():
    candles = _candles([100.0] * 10)
    assert atr(candles, 14) is None
    candles = _candles([100.0 + i for i in range(20)])
    assert atr(candles, 14) is not None


def test_realized_volatility_higher_for_choppier_series():
    calm = [100.0, 100.1, 99.9, 100.05, 99.95] * 5
    choppy = [100.0, 105.0, 95.0, 108.0, 92.0] * 5
    assert realized_volatility(choppy, 20) > realized_volatility(calm, 20)


def test_trend_strength_sign_matches_direction():
    up = [100.0 + i * 0.5 for i in range(40)]
    down = [100.0 - i * 0.5 for i in range(40)]
    atr_up = atr(_candles(up), 14)
    atr_down = atr(_candles(down), 14)
    assert trend_strength(up, atr_up) > 0
    assert trend_strength(down, atr_down) < 0


def test_compute_indicators_returns_none_close_matches_last_close():
    closes = [100.0 + i * 0.2 for i in range(40)]
    candles = _candles(closes)
    ind = compute_indicators(candles)
    assert ind.close == closes[-1]
    assert ind.sma_slow is not None
    assert ind.rsi_14 is not None
