from datetime import datetime, timedelta, timezone

from packages.data.quality import compute_quality_score

NOW = datetime.now(timezone.utc)


def test_fresh_complete_high_quality_data_is_good():
    report = compute_quality_score(
        symbol="BTCUSDT", latest_ts=NOW, timeframe="1m", candle_count=41, expected_count=41,
        last_data_quality="high", provider_connected=True, now=NOW,
    )
    assert report.status == "GOOD"
    assert report.quality_score >= 85


def test_no_data_at_all_is_data_unsafe():
    report = compute_quality_score(
        symbol="BTCUSDT", latest_ts=None, timeframe="1m", candle_count=0, expected_count=41,
        last_data_quality=None, provider_connected=True, now=NOW,
    )
    assert report.status == "DATA_UNSAFE"
    assert report.quality_score == 0
    assert report.detail is not None


def test_disconnected_provider_lowers_score():
    connected = compute_quality_score(
        symbol="BTCUSDT", latest_ts=NOW, timeframe="1m", candle_count=41, expected_count=41,
        last_data_quality="high", provider_connected=True, now=NOW,
    )
    disconnected = compute_quality_score(
        symbol="BTCUSDT", latest_ts=NOW, timeframe="1m", candle_count=41, expected_count=41,
        last_data_quality="high", provider_connected=False, now=NOW,
    )
    assert disconnected.quality_score < connected.quality_score
    assert disconnected.components["source_availability"] == 0.0


def test_stale_latest_candle_lowers_freshness_and_can_flip_to_unsafe():
    fresh = compute_quality_score(
        symbol="ETHUSDT", latest_ts=NOW, timeframe="1m", candle_count=41, expected_count=41,
        last_data_quality="high", provider_connected=True, now=NOW,
    )
    stale = compute_quality_score(
        symbol="ETHUSDT", latest_ts=NOW - timedelta(hours=1), timeframe="1m", candle_count=41,
        expected_count=41, last_data_quality="high", provider_connected=True, now=NOW,
    )
    assert stale.quality_score < fresh.quality_score
    assert stale.components["freshness"] == 0.0


def test_low_completeness_lowers_score():
    full = compute_quality_score(
        symbol="AAPL", latest_ts=NOW, timeframe="1m", candle_count=41, expected_count=41,
        last_data_quality="high", provider_connected=True, now=NOW,
    )
    sparse = compute_quality_score(
        symbol="AAPL", latest_ts=NOW, timeframe="1m", candle_count=5, expected_count=41,
        last_data_quality="high", provider_connected=True, now=NOW,
    )
    assert sparse.quality_score < full.quality_score
    assert sparse.components["completeness"] < 100.0


def test_degraded_data_quality_enum_lowers_consistency():
    report = compute_quality_score(
        symbol="AAPL", latest_ts=NOW, timeframe="1m", candle_count=41, expected_count=41,
        last_data_quality="degraded", provider_connected=True, now=NOW,
    )
    assert report.components["consistency"] == 50.0


def test_score_below_unsafe_threshold_is_data_unsafe_status():
    report = compute_quality_score(
        symbol="XAU", latest_ts=NOW - timedelta(hours=3), timeframe="1m", candle_count=1, expected_count=41,
        last_data_quality="unavailable", provider_connected=False, now=NOW, unsafe_threshold=50,
    )
    assert report.quality_score < 50
    assert report.status == "DATA_UNSAFE"
