from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.data.validation import validate_candle

NOW = datetime.now(timezone.utc)


def _candle(**overrides) -> Candle:
    defaults = dict(ts=NOW, open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0, data_quality="high")
    defaults.update(overrides)
    return Candle(**defaults)


def test_normal_market_candle_is_valid():
    result = validate_candle(_candle(), timeframe="1m", now=NOW)
    assert result.valid is True
    assert result.reasons == []


def test_high_below_low_is_invalid():
    result = validate_candle(_candle(high=98.0, low=99.0), timeframe="1m", now=NOW)
    assert result.valid is False
    assert any("high < low" in r for r in result.reasons)


def test_high_below_open_is_invalid():
    result = validate_candle(_candle(high=99.5, open=100.0), timeframe="1m", now=NOW)
    assert result.valid is False
    assert any("high < open" in r for r in result.reasons)


def test_low_above_close_is_invalid():
    result = validate_candle(_candle(low=101.0, close=100.5), timeframe="1m", now=NOW)
    assert result.valid is False
    assert any("low > close" in r for r in result.reasons)


def test_negative_volume_is_invalid():
    result = validate_candle(_candle(volume=-5.0), timeframe="1m", now=NOW)
    assert result.valid is False
    assert any("negative volume" in r for r in result.reasons)


def test_non_positive_price_is_invalid():
    result = validate_candle(_candle(open=0.0), timeframe="1m", now=NOW)
    assert result.valid is False
    assert any("non-positive price" in r for r in result.reasons)


def test_future_timestamp_is_invalid():
    result = validate_candle(_candle(ts=NOW + timedelta(minutes=5)), timeframe="1m", now=NOW)
    assert result.valid is False
    assert any("future" in r for r in result.reasons)


def test_stale_data_is_invalid():
    result = validate_candle(_candle(ts=NOW - timedelta(hours=2)), timeframe="1m", now=NOW)
    assert result.valid is False
    assert any("stale" in r for r in result.reasons)


def test_recent_data_within_stale_window_is_valid():
    result = validate_candle(_candle(ts=NOW - timedelta(seconds=90)), timeframe="1m", now=NOW)
    assert result.valid is True


def test_absurd_single_bar_move_is_invalid():
    result = validate_candle(_candle(close=200.0, high=201.0), timeframe="1m", previous_close=100.0, now=NOW)
    assert result.valid is False
    assert any("moved" in r for r in result.reasons)


def test_normal_move_vs_previous_close_is_valid():
    result = validate_candle(_candle(), timeframe="1m", previous_close=99.0, now=NOW)
    assert result.valid is True


def test_no_previous_close_skips_jump_check():
    result = validate_candle(_candle(close=100.5), timeframe="1m", previous_close=None, now=NOW)
    assert result.valid is True


def test_stale_window_scales_with_timeframe():
    # A candle 2 hours old is stale for 1m but not for 1D.
    stale_for_1m = validate_candle(_candle(ts=NOW - timedelta(hours=2)), timeframe="1m", now=NOW)
    fine_for_1d = validate_candle(_candle(ts=NOW - timedelta(hours=2)), timeframe="1D", now=NOW)
    assert stale_for_1m.valid is False
    assert fine_for_1d.valid is True
