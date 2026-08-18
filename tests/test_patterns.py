import random
from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.quant.indicators.core import compute_indicators
from packages.quant.patterns.detector import (
    BREAKOUT_POSSIBLE_STRENGTH_CAP,
    BREAKOUT_STATE_CONFIRMED,
    BREAKOUT_STATE_POSSIBLE,
    PATTERN_ANOMALY,
    PATTERN_BREAKOUT,
    PATTERN_MEAN_REVERSION,
    PATTERN_MOMENTUM,
    PATTERN_REVERSAL,
    PATTERN_TREND,
    detect_all,
    detect_anomaly,
    detect_breakout,
    detect_cross_asset,
    detect_mean_reversion,
    detect_momentum,
    detect_reversal,
    detect_trend,
    detect_volatility,
)


def _trend_candles(n=60, step=0.6, volume_spike_at_end=False) -> list[Candle]:
    ts = datetime.now(timezone.utc) - timedelta(minutes=n)
    rng = random.Random(7)
    price = 100.0
    candles = []
    for i in range(n):
        price += step + rng.uniform(-0.05, 0.05)
        volume = 100.0 * (1.5 if volume_spike_at_end and i == n - 1 else 1.0)
        candles.append(Candle(ts=ts + timedelta(minutes=i), open=price - 0.1, high=price + 0.2, low=price - 0.2, close=price, volume=volume))
    return candles


def _flat_candles(n=60, price=100.0) -> list[Candle]:
    ts = datetime.now(timezone.utc) - timedelta(minutes=n)
    return [
        Candle(ts=ts + timedelta(minutes=i), open=price, high=price + 0.02, low=price - 0.02, close=price, volume=100) for i in range(n)
    ]


def test_detect_trend_on_strong_uptrend():
    candles = _trend_candles(step=0.6)
    result = detect_trend(candles, compute_indicators(candles))
    assert result is not None
    assert result.pattern_type == PATTERN_TREND
    assert result.direction == "bullish"


def test_detect_trend_none_when_flat():
    candles = _flat_candles()
    assert detect_trend(candles, compute_indicators(candles)) is None


def test_pattern_confidence_is_separate_from_strength():
    # Prompt 3 §4: "Não confundir os dois" -- a strong trend on all-high-quality
    # data should read high on both, but the two numbers are never the same
    # measurement (strength is magnitude, confidence is data trustworthiness).
    candles = _trend_candles(step=0.6)
    result = detect_trend(candles, compute_indicators(candles))
    assert result is not None
    assert result.confidence == 1.0  # every candle here is data_quality="high"
    assert 0.0 <= result.strength <= 1.0


def test_pattern_confidence_degrades_with_degraded_candles():
    high_quality = _trend_candles(step=0.6)
    degraded = [
        Candle(ts=c.ts, open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume, data_quality="degraded")
        for c in high_quality
    ]
    high_result = detect_trend(high_quality, compute_indicators(high_quality))
    degraded_result = detect_trend(degraded, compute_indicators(degraded))
    assert high_result is not None
    assert degraded_result is not None
    # Same price series -> same strength; only confidence should move.
    assert degraded_result.strength == high_result.strength
    assert degraded_result.confidence < high_result.confidence


def test_detect_breakout_differentiates_confirmed_from_possible():
    # Prompt 3 §8: a breakout without volume confirmation is still real
    # evidence (POSSIBLE_BREAKOUT), just weaker than a volume-confirmed one
    # (CONFIRMED_BREAKOUT) -- neither should be silently dropped to None.
    candles = _trend_candles(step=0.6, volume_spike_at_end=False)
    no_spike = detect_breakout(candles, compute_indicators(candles))
    candles_spike = _trend_candles(step=0.6, volume_spike_at_end=True)
    spike = detect_breakout(candles_spike, compute_indicators(candles_spike))

    assert no_spike is not None
    assert no_spike.pattern_type == PATTERN_BREAKOUT
    assert no_spike.metadata["breakout_state"] == BREAKOUT_STATE_POSSIBLE
    assert no_spike.metadata["volume_confirmed"] is False

    assert spike is not None
    assert spike.pattern_type == PATTERN_BREAKOUT
    assert spike.direction == "bullish"
    assert spike.metadata["breakout_state"] == BREAKOUT_STATE_CONFIRMED
    assert spike.metadata["volume_confirmed"] is True

    # An unconfirmed breakout's strength is capped well below what the raw
    # price move alone would produce -- weaker evidence, not just a
    # different label.
    assert no_spike.strength <= BREAKOUT_POSSIBLE_STRENGTH_CAP


def test_detect_reversal_on_failed_breakout():
    # 40 flat bars (range ~[99.98, 100.02]), then one bar spikes above the
    # range but closes back inside it (without also breaching the low) ->
    # a clean, unambiguous bearish reversal/rejection.
    candles = _flat_candles(n=40, price=100.0)
    ts = candles[-1].ts + timedelta(minutes=1)
    candles.append(Candle(ts=ts, open=100.0, high=103.0, low=100.0, close=100.0, volume=100))
    result = detect_reversal(candles, compute_indicators(candles))
    assert result is not None
    assert result.pattern_type == PATTERN_REVERSAL
    assert result.direction == "bearish"


def test_detect_momentum_aligns_with_strong_move():
    candles = _trend_candles(step=0.8)
    result = detect_momentum(candles, compute_indicators(candles))
    assert result is not None
    assert result.pattern_type == PATTERN_MOMENTUM
    assert result.direction == "bullish"


def test_detect_mean_reversion_bearish_when_overbought():
    candles = _trend_candles(step=0.8)  # RSI pinned near 100 in a clean uptrend
    result = detect_mean_reversion(candles, compute_indicators(candles))
    assert result is not None
    assert result.pattern_type == PATTERN_MEAN_REVERSION
    assert result.direction == "bearish"


def test_detect_volatility_flags_compression_and_expansion():
    calm = _flat_candles()
    calm_result = detect_volatility(calm, compute_indicators(calm))
    assert calm_result is not None
    assert calm_result.metadata["state"] == "compression"

    rng = random.Random(1)
    ts = datetime.now(timezone.utc) - timedelta(minutes=60)
    price = 100.0
    choppy = []
    for i in range(60):
        price *= 1 + rng.uniform(-0.05, 0.05)
        choppy.append(Candle(ts=ts + timedelta(minutes=i), open=price, high=price * 1.02, low=price * 0.98, close=price, volume=100))
    choppy_result = detect_volatility(choppy, compute_indicators(choppy))
    assert choppy_result is not None
    assert choppy_result.metadata["state"] == "expansion"


def test_detect_anomaly_flags_single_bar_outlier():
    # A little natural jitter, not perfectly flat -- perfectly flat bars
    # give the history a return std of exactly 0, which is a legitimately
    # undefined z-score (detector returns None), not a realistic "calm
    # market" input for this specific detector.
    rng = random.Random(5)
    ts = datetime.now(timezone.utc) - timedelta(minutes=41)
    candles = []
    price = 100.0
    for i in range(40):
        price = 100.0 + rng.uniform(-0.1, 0.1)
        candles.append(Candle(ts=ts + timedelta(minutes=i), open=price, high=price + 0.05, low=price - 0.05, close=price, volume=100))
    candles.append(Candle(ts=ts + timedelta(minutes=40), open=100.0, high=112.0, low=100.0, close=112.0, volume=100))  # huge single-bar jump

    result = detect_anomaly(candles, compute_indicators(candles))
    assert result is not None
    assert result.pattern_type == PATTERN_ANOMALY
    assert result.direction == "bullish"


def test_detect_anomaly_none_on_ordinary_bar():
    candles = _flat_candles()
    assert detect_anomaly(candles, compute_indicators(candles)) is None


def test_detect_cross_asset_divergence():
    result = detect_cross_asset(own_return=0.03, peer_return=-0.01, peer_symbol="PEER")
    assert result is not None
    assert result.direction == "bullish"
    assert result.metadata["peer_symbol"] == "PEER"

    assert detect_cross_asset(own_return=0.001, peer_return=0.002, peer_symbol="PEER") is None
    assert detect_cross_asset(own_return=None, peer_return=0.01, peer_symbol="PEER") is None


def test_detect_all_returns_multiple_detections_for_a_trend():
    candles = _trend_candles(step=0.8, volume_spike_at_end=True)
    detections = detect_all(candles, compute_indicators(candles))
    types = {d.pattern_type for d in detections}
    assert PATTERN_TREND in types
    assert all(0.0 <= d.strength <= 1.0 for d in detections)
