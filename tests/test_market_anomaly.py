"""Anomaly Scanner -- "PROMPT 11" §45-49."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.market.anomaly import (
    ANOMALY_CORRELATION_BREAKDOWN,
    ANOMALY_NEWS_SHOCK,
    ANOMALY_PRICE_MOVE,
    ANOMALY_VOLATILITY_SPIKE,
    ANOMALY_VOLUME_SPIKE,
    AnomalyScanner,
)
from packages.market.volatility import REGIME_LOW
from packages.shared.models import (
    OHLCV,
    Anomaly,
    Asset,
    CorrelationMatrixEntry,
    MarketEvent,
    NewsEvent,
    NewsImpact,
    VolatilityEvent,
)

_START = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)
_NOW = _START + timedelta(minutes=30)  # explicit reference passed to scan_asset -- never real wall-clock


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto")
    db_session.add(asset)
    db_session.commit()
    return asset


def _seed_flat_candles(db_session, asset: Asset, count: int = 25, base: float = 100.0) -> None:
    for i in range(count):
        wobble = base + 0.01 * ((i % 2) * 2 - 1)
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=wobble, high=wobble + 0.05,
                low=wobble - 0.05, close=wobble, volume=10.0, data_quality="high",
            )
        )
    db_session.commit()


def test_scan_asset_finds_nothing_on_quiet_data(db_session):
    asset = _asset(db_session, "ANOM_QUIET")
    _seed_flat_candles(db_session, asset)
    findings = AnomalyScanner().scan_asset(db_session, asset.id, asset.symbol, now=_NOW)
    assert findings == []
    assert db_session.query(Anomaly).filter(Anomaly.asset_id == asset.id).count() == 0


def test_scan_asset_detects_price_move_outlier_and_persists_it(db_session):
    asset = _asset(db_session, "ANOM_PRICEMOVE")
    _seed_flat_candles(db_session, asset, count=25)
    # A huge final-bar jump against a near-zero baseline stdev is a clear
    # z-score outlier.
    db_session.add(
        OHLCV(
            asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=25), open=100.0, high=160.0, low=100.0,
            close=150.0, volume=10.0, data_quality="high",
        )
    )
    db_session.commit()

    findings = AnomalyScanner().scan_asset(db_session, asset.id, asset.symbol, now=_NOW)
    types = {f.anomaly_type for f in findings}
    assert ANOMALY_PRICE_MOVE in types
    row = db_session.query(Anomaly).filter(Anomaly.asset_id == asset.id, Anomaly.anomaly_type == ANOMALY_PRICE_MOVE).one()
    assert row.reviewed is False
    assert 0.0 <= row.score <= 100.0


def test_scan_asset_reuses_existing_volume_spike_market_event(db_session):
    asset = _asset(db_session, "ANOM_VOLSPIKE")
    _seed_flat_candles(db_session, asset)
    db_session.add(
        MarketEvent(
            asset_id=asset.id, event_type="VOLUME_SPIKE", timeframe="1m", severity="HIGH", price=100.0, volume=999.0,
            confidence=0.9, meta={"ratio": 5.0}, ts=_START + timedelta(minutes=24),
        )
    )
    db_session.commit()

    findings = AnomalyScanner().scan_asset(db_session, asset.id, asset.symbol, now=_NOW)
    types = {f.anomaly_type for f in findings}
    assert ANOMALY_VOLUME_SPIKE in types
    finding = next(f for f in findings if f.anomaly_type == ANOMALY_VOLUME_SPIKE)
    assert finding.score == 90.0


def test_scan_asset_reuses_volatility_engine_spike_transition(db_session):
    asset = _asset(db_session, "ANOM_VOLATILITY")
    calm = [100.0 + 0.1 * ((i % 2) * 2 - 1) for i in range(60)]
    volatile_tail = [100.0 + 5.0 * ((i % 2) * 2 - 1) for i in range(25)]
    for i, close in enumerate(calm + volatile_tail):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=close, high=close + 0.1,
                low=close - 0.1, close=close, volume=10.0, data_quality="high",
            )
        )
    db_session.add(
        VolatilityEvent(
            asset_id=asset.id, ts=_START - timedelta(hours=1), timeframe="1m", event_type="compression",
            realized_vol=0.001, percentile=5.0, regime=REGIME_LOW,
        )
    )
    db_session.commit()

    findings = AnomalyScanner().scan_asset(db_session, asset.id, asset.symbol, now=_NOW)
    types = {f.anomaly_type for f in findings}
    assert ANOMALY_VOLATILITY_SPIKE in types


def test_scan_asset_detects_correlation_breakdown_against_a_known_peer(db_session):
    asset = _asset(db_session, "ANOM_SELF")
    peer = _asset(db_session, "ANOM_PEER")
    _seed_flat_candles(db_session, asset)
    _seed_flat_candles(db_session, peer)

    # Own asset jumps, peer stays flat -- a real divergence from a
    # historically strongly-correlated peer.
    db_session.add(
        OHLCV(
            asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=25), open=100.0, high=112.0, low=100.0,
            close=110.0, volume=10.0, data_quality="high",
        )
    )
    db_session.add(
        OHLCV(
            asset_id=peer.id, timeframe="1m", ts=_START + timedelta(minutes=25), open=100.0, high=100.1, low=99.9,
            close=100.0, volume=10.0, data_quality="high",
        )
    )
    db_session.add(
        CorrelationMatrixEntry(ts=_START, asset_id_a=asset.id, asset_id_b=peer.id, window_days=30, correlation=0.9)
    )
    db_session.commit()

    findings = AnomalyScanner().scan_asset(db_session, asset.id, asset.symbol, now=_NOW)
    types = {f.anomaly_type for f in findings}
    assert ANOMALY_CORRELATION_BREAKDOWN in types


def test_scan_asset_detects_critical_news_shock(db_session):
    asset = _asset(db_session, "ANOM_NEWS")
    _seed_flat_candles(db_session, asset)
    event = NewsEvent(
        source="Reuters", published_at=_START + timedelta(minutes=20), headline="Critical shock headline",
        category="crypto", sentiment="bearish", importance="critical",
    )
    db_session.add(event)
    db_session.commit()
    db_session.add(
        NewsImpact(
            news_event_id=event.id, asset_id=asset.id, impact="high", direction="bearish", confidence=0.9,
            horizon_hours=6, rationale="test",
        )
    )
    db_session.commit()

    findings = AnomalyScanner().scan_asset(db_session, asset.id, asset.symbol, now=_NOW)
    types = {f.anomaly_type for f in findings}
    assert ANOMALY_NEWS_SHOCK in types
    finding = next(f for f in findings if f.anomaly_type == ANOMALY_NEWS_SHOCK)
    assert finding.score == 75.0
