from datetime import datetime, timedelta, timezone

from apps.worker.market_alerts import MarketAlertTracker
from apps.worker.scanner import run_scan_cycle
from packages.data.connectors.market.base import Candle
from packages.data.connectors.market.mock import MockMarketDataProvider
from packages.shared.models import OHLCV, Alert, Asset, MarketEvent


def test_scan_cycle_stores_candles_for_active_assets_only(db_session):
    # run_scan_cycle scans every active asset in the DB, so this asserts on
    # rows scoped to its own assets rather than the aggregate summary counts,
    # which other tests' active assets also contribute to in the full suite.
    active = Asset(symbol="TESTBTC", asset_class="crypto", is_active=True)
    inactive = Asset(symbol="TESTOLD", asset_class="crypto", is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()

    summary = run_scan_cycle(db_session, MockMarketDataProvider())

    assert summary["stored"] >= 1
    assert summary["unavailable"] == 0

    stored = db_session.query(OHLCV).filter(OHLCV.asset_id == active.id).all()
    assert len(stored) == 1
    assert stored[0].data_quality == "high"

    assert db_session.query(OHLCV).filter(OHLCV.asset_id == inactive.id).count() == 0


class _FixedCandleProvider:
    """Always returns the same pre-built Candle, so tests can hand it
    something invalid/stale without depending on the mock provider's
    random walk."""

    name = "fixed"

    def __init__(self, candle: Candle | None) -> None:
        self._candle = candle
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        return self._candle

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        return [self._candle] if self._candle else []


class _RaisingProvider:
    """Simulates a provider whose API call itself throws (network error,
    malformed response, rate limit) rather than returning None."""

    name = "raising"

    def is_connected(self) -> bool:
        return True

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        raise RuntimeError("simulated provider outage")

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        raise RuntimeError("simulated provider outage")


class _DisconnectedProvider:
    name = "disconnected"

    def is_connected(self) -> bool:
        return False

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        raise AssertionError("should never be called once is_connected() is False")

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        raise AssertionError("should never be called once is_connected() is False")


def test_scan_cycle_rejects_invalid_candle_and_raises_market_event(db_session):
    asset = Asset(symbol="TESTINVALID", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    bad_candle = Candle(
        ts=datetime.now(timezone.utc), open=100.0, high=90.0, low=99.0,  # high < low, high < open
        close=100.0, volume=10.0, data_quality="high",
    )
    summary = run_scan_cycle(db_session, _FixedCandleProvider(bad_candle))

    assert summary["stored"] == 0
    assert summary["invalid"] == 1
    assert summary["unavailable"] == 1
    assert db_session.query(OHLCV).filter(OHLCV.asset_id == asset.id).count() == 0

    events = db_session.query(MarketEvent).filter(MarketEvent.asset_id == asset.id).all()
    assert len(events) == 1
    assert events[0].event_type == "INVALID_MARKET_DATA"

    alerts = db_session.query(Alert).filter(Alert.category == "market").all()
    assert len(alerts) == 1
    assert "TESTINVALID" in alerts[0].message


def test_scan_cycle_rejects_stale_candle(db_session):
    asset = Asset(symbol="TESTSTALE", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    stale_candle = Candle(
        ts=datetime.now(timezone.utc) - timedelta(hours=2), open=100.0, high=101.0, low=99.0,
        close=100.5, volume=10.0, data_quality="high",
    )
    summary = run_scan_cycle(db_session, _FixedCandleProvider(stale_candle))

    assert summary["stored"] == 0
    assert summary["invalid"] == 1
    assert db_session.query(OHLCV).filter(OHLCV.asset_id == asset.id).count() == 0


def test_scan_cycle_survives_a_provider_raising_for_one_asset(db_session):
    good = Asset(symbol="TESTGOOD", asset_class="crypto", is_active=True)
    db_session.add(good)
    db_session.commit()

    summary = run_scan_cycle(db_session, _RaisingProvider())

    # The provider raised for every asset, but the batch itself completed
    # instead of propagating the exception -- "falha de provider não
    # derruba o sistema".
    assert summary["scanned"] == 1
    assert summary["stored"] == 0
    assert summary["unavailable"] == 1

    alerts = db_session.query(Alert).filter(Alert.category == "market").all()
    assert any("TESTGOOD" in a.message for a in alerts)


def test_scan_cycle_skips_entirely_when_provider_disconnected(db_session):
    asset = Asset(symbol="TESTDISCONNECTED", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    summary = run_scan_cycle(db_session, _DisconnectedProvider())

    assert summary["scanned"] == 0
    assert summary["stored"] == 0
    assert summary["unavailable"] == 1  # counts the one asset that couldn't be scanned

    alerts = db_session.query(Alert).filter(Alert.category == "market").all()
    assert len(alerts) == 1
    assert "disconnected" in alerts[0].message.lower()


def test_scan_cycle_alerting_is_debounced_across_cycles(db_session):
    asset = Asset(symbol="TESTDEBOUNCE", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()

    tracker = MarketAlertTracker(cooldown_seconds=900)
    run_scan_cycle(db_session, _DisconnectedProvider(), tracker)
    run_scan_cycle(db_session, _DisconnectedProvider(), tracker)
    run_scan_cycle(db_session, _DisconnectedProvider(), tracker)

    alerts = db_session.query(Alert).filter(Alert.category == "market").all()
    assert len(alerts) == 1
