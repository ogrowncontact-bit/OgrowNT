"""Pairs Research -- "PROMPT 11" §36-38."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.market.pairs import (
    analyze_pair,
    compute_spread_series,
    hedge_ratio,
    lag1_autocorrelation,
    scan_correlated_universe,
    zscore_of_latest,
)
from packages.shared.models import OHLCV, Asset, CorrelationMatrixEntry

_START = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)


def test_hedge_ratio_recovers_an_exact_linear_relationship():
    closes_b = [100.0 + i for i in range(30)]
    closes_a = [2.0 * v for v in closes_b]
    beta = hedge_ratio(closes_a, closes_b)
    assert beta is not None
    assert abs(beta - 2.0) < 1e-9


def test_hedge_ratio_none_with_too_few_points():
    assert hedge_ratio([1.0, 2.0], [1.0, 2.0]) is None


def test_compute_spread_series_matches_manual_calculation():
    closes_a = [10.0, 20.0, 30.0]
    closes_b = [1.0, 2.0, 3.0]
    spread = compute_spread_series(closes_a, closes_b, beta=5.0)
    assert spread == [10.0 - 5.0, 20.0 - 10.0, 30.0 - 15.0]


def test_zscore_of_latest_flags_a_clear_outlier():
    history = list(range(1, 20))  # 1..19, mean 10, modest spread
    series = history + [100.0]
    z = zscore_of_latest(series)
    assert z is not None
    assert z > 5.0


def test_zscore_of_latest_none_with_too_few_points():
    assert zscore_of_latest([1.0] * 5) is None


def test_lag1_autocorrelation_high_for_a_persistent_trend():
    series = [float(i) for i in range(30)]
    autocorr = lag1_autocorrelation(series)
    assert autocorr is not None
    assert autocorr >= 0.9


def test_lag1_autocorrelation_negative_for_a_strictly_alternating_series():
    series = [0.0, 10.0] * 15
    autocorr = lag1_autocorrelation(series)
    assert autocorr is not None
    assert autocorr < 0.0


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto")
    db_session.add(asset)
    db_session.commit()
    return asset


def _seed(db_session, asset: Asset, closes: list[float]) -> None:
    for i, close in enumerate(closes):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=close, high=close + 0.1,
                low=close - 0.1, close=close, volume=10.0, data_quality="high",
            )
        )
    db_session.commit()


def test_analyze_pair_detects_a_notable_spread_deviation(db_session):
    asset_a = _asset(db_session, "PAIR_A")
    asset_b = _asset(db_session, "PAIR_B")
    closes_b = [100.0 + i * 0.1 for i in range(150)]
    closes_a = [2.0 * v for v in closes_b]
    closes_a[-1] += 500.0  # a real, sudden divergence on the last bar
    _seed(db_session, asset_a, closes_a)
    _seed(db_session, asset_b, closes_b)

    signal = analyze_pair(db_session, asset_a.id, asset_a.symbol, asset_b.id, asset_b.symbol)
    assert signal is not None
    assert signal.symbol_a == "PAIR_A" and signal.symbol_b == "PAIR_B"
    assert abs(signal.zscore) >= 2.0
    assert signal.sample_size == 150
    assert "not an execution signal" in signal.disclaimer


def test_analyze_pair_returns_none_for_a_well_behaved_pair(db_session):
    asset_a = _asset(db_session, "PAIR_QUIET_A")
    asset_b = _asset(db_session, "PAIR_QUIET_B")
    closes_b = [100.0 + 0.01 * ((i % 3) - 1) for i in range(150)]
    closes_a = [2.0 * v for v in closes_b]
    _seed(db_session, asset_a, closes_a)
    _seed(db_session, asset_b, closes_b)

    signal = analyze_pair(db_session, asset_a.id, asset_a.symbol, asset_b.id, asset_b.symbol)
    assert signal is None


def test_scan_correlated_universe_only_analyzes_pairs_above_threshold(db_session):
    strong_a = _asset(db_session, "SCAN_STRONG_A")
    strong_b = _asset(db_session, "SCAN_STRONG_B")
    weak_a = _asset(db_session, "SCAN_WEAK_A")
    weak_b = _asset(db_session, "SCAN_WEAK_B")

    closes_b = [100.0 + i * 0.1 for i in range(150)]
    closes_a = [2.0 * v for v in closes_b]
    closes_a[-1] += 500.0
    _seed(db_session, strong_a, closes_a)
    _seed(db_session, strong_b, closes_b)
    _seed(db_session, weak_a, [100.0] * 150)
    _seed(db_session, weak_b, [50.0] * 150)

    db_session.add(
        CorrelationMatrixEntry(ts=_START, asset_id_a=strong_a.id, asset_id_b=strong_b.id, window_days=30, correlation=0.95)
    )
    db_session.add(
        CorrelationMatrixEntry(ts=_START, asset_id_a=weak_a.id, asset_id_b=weak_b.id, window_days=30, correlation=0.1)
    )
    db_session.commit()

    signals = scan_correlated_universe(
        db_session, [strong_a.id, strong_b.id, weak_a.id, weak_b.id], correlation_threshold=0.7,
    )
    symbol_pairs = {(s.symbol_a, s.symbol_b) for s in signals}
    assert ("SCAN_STRONG_A", "SCAN_STRONG_B") in symbol_pairs
    assert not any("SCAN_WEAK" in a or "SCAN_WEAK" in b for a, b in symbol_pairs)


def test_scan_correlated_universe_with_fewer_than_two_assets_is_empty(db_session):
    asset = _asset(db_session, "SCAN_LONELY")
    assert scan_correlated_universe(db_session, [asset.id]) == []
