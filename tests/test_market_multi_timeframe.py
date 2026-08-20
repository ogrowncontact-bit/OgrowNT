"""Multi-Timeframe Engine -- "PROMPT 11" §39-43."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.data.connectors.market.base import Candle
from packages.market.multi_timeframe import (
    AGREEMENT,
    CONFLICT,
    INSUFFICIENT_DATA,
    NEUTRAL,
    TREND_BEARISH,
    TREND_BULLISH,
    MultiTimeframeEngine,
    resample_candles,
)
from packages.shared.models import OHLCV, Asset

_START = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)


def _minute_candle(minute: int, close: float) -> Candle:
    return Candle(
        ts=_START + timedelta(minutes=minute), open=close, high=close + 0.5, low=close - 0.5, close=close,
        volume=10.0, data_quality="high",
    )


def test_resample_candles_1m_is_identity():
    candles = [_minute_candle(i, 100.0 + i) for i in range(5)]
    assert resample_candles(candles, "1m") == candles


def test_resample_candles_aggregates_complete_buckets_and_drops_partial():
    # Aligned to epoch: 1970-01-01 is minute 0, so any UTC minute-of-epoch
    # divisible by 5 is a clean 5m boundary. _START is arbitrary but every
    # test only cares about internal consistency, not wall-clock alignment,
    # so we align explicitly here.
    epoch_minute = int(_START.timestamp() // 60)
    aligned_start = _START - timedelta(minutes=epoch_minute % 5)
    closes = list(range(100, 112))  # 12 one-minute candles -> 2 complete 5m buckets + 2 leftover
    candles = [
        Candle(
            ts=aligned_start + timedelta(minutes=i), open=float(c), high=float(c), low=float(c), close=float(c),
            volume=10.0, data_quality="high",
        )
        for i, c in enumerate(closes)
    ]
    bars = resample_candles(candles, "5m")
    assert len(bars) == 2
    assert bars[0].open == 100.0 and bars[0].close == 104.0 and bars[0].volume == 50.0
    assert bars[1].open == 105.0 and bars[1].close == 109.0 and bars[1].volume == 50.0


def test_resample_candles_mixed_quality_degrades_honestly():
    epoch_minute = int(_START.timestamp() // 60)
    aligned_start = _START - timedelta(minutes=epoch_minute % 5)
    candles = [
        Candle(
            ts=aligned_start + timedelta(minutes=i), open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0,
            data_quality="degraded" if i == 2 else "high",
        )
        for i in range(5)
    ]
    bars = resample_candles(candles, "5m")
    assert len(bars) == 1
    assert bars[0].data_quality == "degraded"


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto")
    db_session.add(asset)
    db_session.commit()
    return asset


def _seed(db_session, asset: Asset, closes: list[float]) -> None:
    for i, close in enumerate(closes):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=close, high=close + 0.5,
                low=close - 0.5, close=close, volume=10.0, data_quality="high",
            )
        )
    db_session.commit()


def test_analyze_reports_insufficient_data_with_almost_no_history(db_session):
    asset = _asset(db_session, "MTF_THIN")
    _seed(db_session, asset, [100.0])
    result = MultiTimeframeEngine().analyze(db_session, asset.id, asset.symbol)
    assert result.agreement_state == INSUFFICIENT_DATA
    assert all(not r.available for r in result.readings)


def test_analyze_reports_agreement_on_a_steady_uptrend(db_session):
    asset = _asset(db_session, "MTF_UPTREND")
    closes = [100.0 + i for i in range(20)]  # steady, unambiguous uptrend
    _seed(db_session, asset, closes)
    result = MultiTimeframeEngine().analyze(db_session, asset.id, asset.symbol)
    assert result.agreement_state == AGREEMENT
    assert result.agreeing_direction == TREND_BULLISH


def test_analyze_reports_neutral_on_flat_prices(db_session):
    asset = _asset(db_session, "MTF_FLAT")
    _seed(db_session, asset, [100.0] * 20)
    result = MultiTimeframeEngine().analyze(db_session, asset.id, asset.symbol)
    assert result.agreement_state == NEUTRAL
    assert result.agreeing_direction is None


def test_analyze_reports_explicit_conflict_never_averaged_away(db_session):
    asset = _asset(db_session, "MTF_CONFLICT")
    closes = []
    for i in range(40):  # smooth decline from 700 -> 250
        closes.append(700.0 - i * (700.0 - 250.0) / 39.0)
    for i in range(40, 45):  # sharp 5-minute bounce back up to 300
        closes.append(250.0 + (i - 39) * (300.0 - 250.0) / 5.0)
    _seed(db_session, asset, closes)

    result = MultiTimeframeEngine().analyze(db_session, asset.id, asset.symbol)
    assert result.agreement_state == CONFLICT
    assert result.agreeing_direction is None
    directions = {r.timeframe: r.direction for r in result.readings if r.available}
    assert directions["1m"] == TREND_BULLISH
    assert directions["15m"] == TREND_BEARISH
