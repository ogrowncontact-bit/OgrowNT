"""Market Universe Manager -- "PROMPT 11" §5-10, §67-70."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.market.universe import (
    STATUS_ACTIVE,
    STATUS_DATA_UNAVAILABLE,
    STATUS_INACTIVE,
    STATUS_LOW_LIQUIDITY,
    STATUS_QUARANTINED,
    MarketUniverseManager,
    is_paper_eligible,
    register_discovered_asset,
)
from packages.shared.models import OHLCV, Asset, MarketEvent

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


class _StubProvider:
    name = "stub"

    def __init__(self, connected: bool = True):
        self._connected = connected

    def is_connected(self) -> bool:
        return self._connected

    def get_latest_candle(self, symbol, timeframe):  # pragma: no cover - unused by universe.py
        return None

    def get_recent_candles(self, symbol, timeframe, limit):  # pragma: no cover - unused by universe.py
        return []


def _asset(db_session, symbol: str, **overrides) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", **overrides)
    db_session.add(asset)
    db_session.commit()
    return asset


def _seed_ohlcv(db_session, asset: Asset, *, count: int, ts: datetime, volume: float, quality: str = "high"):
    for i in range(count):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=ts - timedelta(minutes=count - i), open=100.0, high=101.0,
                low=99.0, close=100.0, volume=volume, data_quality=quality,
            )
        )
    db_session.commit()


def test_evaluate_asset_with_no_ohlcv_is_data_unavailable(db_session):
    asset = _asset(db_session, "UNIV_NO_DATA")
    manager = MarketUniverseManager()
    evaluation = manager.evaluate_asset(db_session, asset, now=_NOW)
    assert evaluation.status == STATUS_DATA_UNAVAILABLE
    assert asset.status == STATUS_DATA_UNAVAILABLE
    assert is_paper_eligible(asset) is False


def test_evaluate_asset_fresh_good_data_and_strong_peers_is_active_and_paper_eligible(db_session):
    asset = _asset(db_session, "UNIV_GOOD")
    _seed_ohlcv(db_session, asset, count=20, ts=_NOW, volume=500.0, quality="high")
    manager = MarketUniverseManager()
    evaluation = manager.evaluate_asset(db_session, asset, peer_avg_volumes=[500.0, 500.0, 500.0], now=_NOW)
    assert evaluation.status == STATUS_ACTIVE
    assert evaluation.paper_eligible is True
    assert is_paper_eligible(asset) is True
    assert asset.liquidity_score is not None
    assert asset.data_quality_score is not None


def test_evaluate_asset_weak_peers_and_degraded_quality_is_low_liquidity(db_session):
    asset = _asset(db_session, "UNIV_THIN")
    # One stale, degraded, incomplete candle -> quality score lands in the
    # DEGRADED band (not DATA_UNSAFE), and a volume far below its peers ->
    # percentile 0. Combined liquidity average falls below the UNTRADABLE floor.
    _seed_ohlcv(db_session, asset, count=1, ts=_NOW - timedelta(minutes=10), volume=1.0, quality="degraded")
    manager = MarketUniverseManager()
    evaluation = manager.evaluate_asset(
        db_session, asset, peer_avg_volumes=[1000.0, 2000.0, 3000.0], provider_connected=True, now=_NOW,
    )
    assert evaluation.status == STATUS_LOW_LIQUIDITY
    assert evaluation.liquidity_tier == "untradable"
    assert is_paper_eligible(asset) is False


def test_evaluate_asset_quarantines_on_repeated_invalid_market_data(db_session):
    asset = _asset(db_session, "UNIV_BAD_FEED")
    _seed_ohlcv(db_session, asset, count=5, ts=_NOW, volume=500.0, quality="high")
    for _ in range(3):
        db_session.add(
            MarketEvent(
                asset_id=asset.id, event_type="INVALID_MARKET_DATA", timeframe="1m", severity="MEDIUM",
                price=100.0, volume=1.0, confidence=1.0, meta={}, ts=_NOW - timedelta(minutes=5),
            )
        )
    db_session.commit()
    manager = MarketUniverseManager()
    evaluation = manager.evaluate_asset(db_session, asset, peer_avg_volumes=[500.0], now=_NOW)
    assert evaluation.status == STATUS_QUARANTINED
    assert "corrupted" in evaluation.reasons[0] or "suspicious" in evaluation.reasons[0]


def test_run_universe_evaluation_cycle_skips_operator_controlled_assets(db_session):
    active = _asset(db_session, "UNIV_CYCLE_ACTIVE")
    _seed_ohlcv(db_session, active, count=20, ts=_NOW, volume=500.0, quality="high")
    inactive = _asset(db_session, "UNIV_CYCLE_INACTIVE", status=STATUS_INACTIVE)

    manager = MarketUniverseManager()
    results = manager.run_universe_evaluation_cycle(db_session, _StubProvider(), now=_NOW)

    result_symbols = {r.symbol for r in results}
    assert "UNIV_CYCLE_ACTIVE" in result_symbols
    assert "UNIV_CYCLE_INACTIVE" not in result_symbols
    db_session.refresh(inactive)
    assert inactive.status == STATUS_INACTIVE  # untouched
    assert inactive.liquidity_score is None  # never evaluated


def test_register_discovered_asset_is_idempotent(db_session):
    first = register_discovered_asset(db_session, "UNIV_NEW_SYMBOL", "crypto")
    assert first.status == STATUS_DATA_UNAVAILABLE
    second = register_discovered_asset(db_session, "UNIV_NEW_SYMBOL", "crypto")
    assert second.id == first.id
    assert db_session.query(Asset).filter(Asset.symbol == "UNIV_NEW_SYMBOL").count() == 1


def test_is_paper_eligible_false_for_every_non_active_status(db_session):
    for status in (STATUS_DATA_UNAVAILABLE, STATUS_LOW_LIQUIDITY, STATUS_QUARANTINED, STATUS_INACTIVE):
        asset = Asset(symbol=f"UNIV_STATUS_{status}", asset_class="crypto", status=status)
        assert is_paper_eligible(asset) is False
