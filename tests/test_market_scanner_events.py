from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.quant.market.events import (
    EVENT_ANOMALY,
    EVENT_BREAKOUT_CANDIDATE,
    EVENT_MOMENTUM_CHANGE,
    EVENT_PRICE_MOVEMENT,
    EVENT_TREND_CHANGE,
    EVENT_VOLATILITY_SPIKE,
    EVENT_VOLUME_SPIKE,
    detect_events,
)

BASE_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _flat_candles(n: int, price: float = 100.0, volume: float = 100.0) -> list[Candle]:
    """A quiet, unmoving market -- the baseline every test starts from and
    the "normal market produces no events" case on its own."""
    return [
        Candle(
            ts=BASE_TS + timedelta(minutes=i), open=price, high=price + 0.05, low=price - 0.05,
            close=price, volume=volume, data_quality="high",
        )
        for i in range(n)
    ]


def _append(candles: list[Candle], **overrides) -> list[Candle]:
    last = candles[-1]
    defaults = dict(
        ts=last.ts + timedelta(minutes=1), open=last.close, high=last.close + 0.05,
        low=last.close - 0.05, close=last.close, volume=last.volume, data_quality="high",
    )
    defaults.update(overrides)
    return candles + [Candle(**defaults)]


def test_normal_flat_market_produces_no_events():
    candles = _flat_candles(35)
    assert detect_events(candles) == []


def test_not_enough_history_produces_no_events():
    candles = _flat_candles(10)  # below MIN_CANDLES_REQUIRED
    assert detect_events(candles) == []


def test_price_movement_event_on_large_single_bar_move():
    candles = _flat_candles(35)
    candles = _append(candles, close=106.0, high=106.2, low=99.9)  # +6% in one bar
    events = detect_events(candles)
    price_events = [e for e in events if e.event_type == EVENT_PRICE_MOVEMENT]
    assert len(price_events) == 1
    assert price_events[0].severity == "HIGH"


def test_volume_spike_event_on_large_volume_ratio():
    candles = _flat_candles(35, volume=100.0)
    candles = _append(candles, volume=1200.0)  # 12x the 100-volume baseline
    events = detect_events(candles)
    volume_events = [e for e in events if e.event_type == EVENT_VOLUME_SPIKE]
    assert len(volume_events) == 1
    assert volume_events[0].severity == "CRITICAL"


def test_breakout_candidate_event_above_recent_high():
    candles = _flat_candles(35, price=100.0)
    candles = _append(candles, close=110.0, high=110.2, low=99.9)  # well above the 100.05 recent high
    events = detect_events(candles)
    breakout_events = [e for e in events if e.event_type == EVENT_BREAKOUT_CANDIDATE]
    assert len(breakout_events) == 1
    assert breakout_events[0].metadata["direction"] == "up"


def test_breakout_candidate_event_below_recent_low():
    candles = _flat_candles(35, price=100.0)
    candles = _append(candles, close=90.0, high=90.2, low=89.8)  # well below the 99.95 recent low
    events = detect_events(candles)
    breakout_events = [e for e in events if e.event_type == EVENT_BREAKOUT_CANDIDATE]
    assert len(breakout_events) == 1
    assert breakout_events[0].metadata["direction"] == "down"


def _wobbling_baseline(n: int, price: float = 100.0) -> list[Candle]:
    """A near-flat window with a tiny alternating wobble -- non-zero but
    much quieter than the spike window below, so the ratio is finite."""
    candles = []
    p = price
    for i in range(n):
        p = p * (1.0005 if i % 2 == 0 else 0.9995)
        candles.append(
            Candle(
                ts=BASE_TS + timedelta(minutes=i), open=p, high=p + 0.05, low=p - 0.05,
                close=round(p, 4), volume=100.0, data_quality="high",
            )
        )
    return candles


def test_volatility_spike_event_when_recent_range_widens():
    candles = _wobbling_baseline(21, price=100.0)
    # A calm baseline window, then a turbulent recent window (alternating
    # sharp swings) -- realized_volatility over the recent 20 bars should
    # be far higher than over the prior (near-flat) 20.
    price = candles[-1].close
    for i in range(20):
        price = price * (1.05 if i % 2 == 0 else 0.95)
        candles = _append(candles, close=round(price, 4), high=round(price * 1.02, 4), low=round(price * 0.98, 4))
    events = detect_events(candles)
    vol_events = [e for e in events if e.event_type == EVENT_VOLATILITY_SPIKE]
    assert len(vol_events) == 1
    assert vol_events[0].severity == "CRITICAL"


def test_anomaly_event_on_huge_single_bar_range():
    candles = _flat_candles(35, price=100.0)
    # A bar whose range vastly exceeds the near-zero ATR baseline, but is
    # still internally coherent (passes validate_candle).
    candles = _append(candles, open=100.0, high=115.0, low=95.0, close=101.0)
    events = detect_events(candles)
    anomaly_events = [e for e in events if e.event_type == EVENT_ANOMALY]
    assert len(anomaly_events) == 1
    assert anomaly_events[0].severity in {"MEDIUM", "HIGH", "CRITICAL"}


def test_momentum_change_event_on_roc_sign_flip():
    # A flat run establishes the 10-bars-ago reference point, then a rise
    # brings the 10-period ROC positive, and one sharp final drop crosses
    # the newest close back below that reference -- flipping ROC negative
    # only on the very last bar (the sign-flip detect_events looks for).
    candles = _flat_candles(25, price=100.0)
    price = 100.0
    for _ in range(9):
        price *= 1.01
        candles = _append(candles, close=round(price, 4), high=round(price * 1.002, 4), low=round(price * 0.998, 4))
    candles = _append(candles, close=90.0, high=91.0, low=89.5)
    events = detect_events(candles)
    momentum_events = [e for e in events if e.event_type == EVENT_MOMENTUM_CHANGE]
    assert len(momentum_events) == 1


def test_trend_change_event_on_trend_strength_sign_flip():
    # A strong 20-bar uptrend (EMA fast well above EMA slow), then exactly
    # enough sharp down-bars to cross EMA fast back below EMA slow on the
    # newest bar only -- trend_strength flips sign right at the last candle.
    candles = _flat_candles(5, price=100.0)
    price = 100.0
    for _ in range(20):
        price *= 1.02
        candles = _append(candles, close=round(price, 4), high=round(price * 1.003, 4), low=round(price * 0.997, 4))
    for _ in range(9):
        price *= 0.96
        candles = _append(candles, close=round(price, 4), high=round(price * 1.003, 4), low=round(price * 0.997, 4))
    events = detect_events(candles)
    trend_events = [e for e in events if e.event_type == EVENT_TREND_CHANGE]
    assert len(trend_events) == 1
