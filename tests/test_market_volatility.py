"""Volatility Engine -- "PROMPT 11" §54-57."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.market.volatility import (
    EVENT_COLLAPSE,
    EVENT_COMPRESSION,
    EVENT_EXPANSION,
    EVENT_SPIKE,
    REGIME_EXTREME,
    REGIME_HIGH,
    REGIME_LOW,
    REGIME_NORMAL,
    VolatilityEngine,
    _classify_transition,
    _rolling_volatility_series,
    regime_for_percentile,
)
from packages.shared.models import OHLCV, Asset, VolatilityEvent

_START = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)


def test_regime_for_percentile_boundaries():
    assert regime_for_percentile(10.0) == REGIME_LOW
    assert regime_for_percentile(50.0) == REGIME_NORMAL
    assert regime_for_percentile(85.0) == REGIME_HIGH
    assert regime_for_percentile(99.0) == REGIME_EXTREME


def test_classify_transition_no_previous_is_not_an_event():
    assert _classify_transition(None, REGIME_EXTREME) is None


def test_classify_transition_same_regime_is_not_an_event():
    assert _classify_transition(REGIME_NORMAL, REGIME_NORMAL) is None


def test_classify_transition_adjacent_up_is_expansion():
    assert _classify_transition(REGIME_LOW, REGIME_NORMAL) == EVENT_EXPANSION


def test_classify_transition_adjacent_down_is_compression():
    assert _classify_transition(REGIME_HIGH, REGIME_NORMAL) == EVENT_COMPRESSION


def test_classify_transition_two_tier_jump_up_is_spike():
    assert _classify_transition(REGIME_LOW, REGIME_HIGH) == EVENT_SPIKE
    assert _classify_transition(REGIME_LOW, REGIME_EXTREME) == EVENT_SPIKE


def test_classify_transition_two_tier_jump_down_is_collapse():
    assert _classify_transition(REGIME_EXTREME, REGIME_LOW) == EVENT_COLLAPSE
    assert _classify_transition(REGIME_HIGH, REGIME_LOW) == EVENT_COLLAPSE


def test_rolling_volatility_series_length_matches_available_windows():
    closes = [100.0 + (i % 3) for i in range(40)]
    series = _rolling_volatility_series(closes, period=20)
    assert len(series) == 40 - 20


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto")
    db_session.add(asset)
    db_session.commit()
    return asset


def _seed_candles(db_session, asset: Asset, closes: list[float]) -> None:
    for i, close in enumerate(closes):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=close, high=close + 0.1,
                low=close - 0.1, close=close, volume=10.0, data_quality="high",
            )
        )
    db_session.commit()


def test_analyze_reports_unavailable_with_too_few_candles(db_session):
    asset = _asset(db_session, "VOL_THIN")
    _seed_candles(db_session, asset, [100.0] * 10)
    reading = VolatilityEngine().analyze(db_session, asset.id, asset.symbol)
    assert reading.available is False
    assert reading.regime is None


def test_analyze_never_persists_an_event_on_the_first_ever_reading(db_session):
    asset = _asset(db_session, "VOL_FIRST")
    closes = [100.0 * (1.0 + 0.05 * (-1) ** i) for i in range(85)]  # choppy but consistent throughout
    _seed_candles(db_session, asset, closes)
    reading = VolatilityEngine().analyze(db_session, asset.id, asset.symbol)
    assert reading.available is True
    assert reading.event_type is None  # no prior regime to transition from
    assert db_session.query(VolatilityEvent).filter(VolatilityEvent.asset_id == asset.id).count() == 0


def test_analyze_persists_a_spike_event_on_a_real_regime_jump(db_session):
    asset = _asset(db_session, "VOL_SPIKE")
    calm = [100.0 + 0.1 * ((i % 2) * 2 - 1) for i in range(60)]  # tiny +/-0.1 oscillation
    volatile_tail = [100.0 + 5.0 * ((i % 2) * 2 - 1) for i in range(25)]  # +/-5 oscillation
    _seed_candles(db_session, asset, calm + volatile_tail)

    # Simulate this asset having already been tracked in a LOW regime.
    db_session.add(
        VolatilityEvent(
            asset_id=asset.id, ts=_START - timedelta(hours=1), timeframe="1m", event_type=EVENT_COMPRESSION,
            realized_vol=0.001, percentile=5.0, regime=REGIME_LOW,
        )
    )
    db_session.commit()

    reading = VolatilityEngine().analyze(db_session, asset.id, asset.symbol)
    assert reading.available is True
    assert reading.percentile is not None and reading.percentile >= 90.0
    assert reading.regime in (REGIME_HIGH, REGIME_EXTREME)
    assert reading.event_type in (EVENT_EXPANSION, EVENT_SPIKE)

    rows = db_session.query(VolatilityEvent).filter(VolatilityEvent.asset_id == asset.id).order_by(VolatilityEvent.ts).all()
    assert len(rows) == 2
    assert rows[-1].regime == reading.regime
    assert rows[-1].event_type == reading.event_type


def test_analyze_persists_no_new_row_when_regime_is_unchanged(db_session):
    asset = _asset(db_session, "VOL_STABLE")
    closes = [100.0 + 0.1 * ((i % 2) * 2 - 1) for i in range(85)]
    _seed_candles(db_session, asset, closes)

    first = VolatilityEngine().analyze(db_session, asset.id, asset.symbol)
    assert first.event_type is None  # first-ever reading, no prior regime

    # Manually plant a prior event matching the SAME regime the next
    # reading will compute, so the second call should see "no transition".
    db_session.add(
        VolatilityEvent(
            asset_id=asset.id, ts=_START - timedelta(minutes=1), timeframe="1m", event_type=EVENT_COMPRESSION,
            realized_vol=first.realized_vol, percentile=first.percentile, regime=first.regime,
        )
    )
    db_session.commit()
    before = db_session.query(VolatilityEvent).filter(VolatilityEvent.asset_id == asset.id).count()

    second = VolatilityEngine().analyze(db_session, asset.id, asset.symbol)
    assert second.event_type is None
    after = db_session.query(VolatilityEvent).filter(VolatilityEvent.asset_id == asset.id).count()
    assert after == before
