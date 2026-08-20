"""Global Market Intelligence cadence -- "PROMPT 11" §92 (apps/worker wiring)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.worker.market_intelligence import run_market_intelligence_cycle, run_universe_cycle
from packages.data.connectors.market.mock import MockMarketDataProvider
from packages.market.opportunity_types import BREAKOUT
from packages.shared.models import (
    OHLCV,
    Anomaly,
    Asset,
    CorrelationMatrixEntry,
    OpportunityCluster,
    Signal,
    StrategyRow,
    WatchlistEntry,
)

_START = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)
_NOW = _START + timedelta(minutes=17)

# The same hand-verified zigzag used in tests/test_market_structure.py:
# swing high 50 -> swing low 20 -> swing high 60 (HH) -> swing low 30 (HL)
# -- an intact uptrend -- plus a final close above 60 to trigger a genuine
# BREAK_OF_STRUCTURE (-> BREAKOUT classification).
_ZIGZAG_BREAKOUT = [10, 20, 30, 40, 50, 40, 30, 20, 25, 35, 45, 60, 45, 35, 30, 35, 40, 75]


def _asset(db_session, symbol: str) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto")
    db_session.add(asset)
    db_session.commit()
    return asset


def _seed_candles(db_session, asset: Asset, closes: list[float]) -> None:
    for i, close in enumerate(closes):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=close, high=close + 0.5,
                low=close - 0.5, close=close, volume=500.0, data_quality="high",
            )
        )
    db_session.commit()


def test_run_universe_cycle_evaluates_assets_and_reports_transitions(db_session):
    asset = _asset(db_session, "MKTINT_UNIVERSE")
    _seed_candles(db_session, asset, [100.0] * 25)
    result = run_universe_cycle(db_session, MockMarketDataProvider())
    assert result["evaluated"] >= 1
    db_session.refresh(asset)
    assert asset.status is not None


def test_run_market_intelligence_cycle_returns_a_summary_and_does_not_crash_on_thin_data(db_session):
    asset = _asset(db_session, "MKTINT_THIN")
    _seed_candles(db_session, asset, [100.0] * 5)  # too thin for most engines -- must degrade honestly, not crash
    result = run_market_intelligence_cycle(db_session, top_n=20, now=_NOW)
    assert set(result) == {"scanned", "anomalies_found", "volatility_events_found", "clusters_found"}


def test_run_market_intelligence_cycle_enriches_an_open_signal_with_opportunity_type(db_session):
    asset = _asset(db_session, "MKTINT_BREAKOUT")
    _seed_candles(db_session, asset, [float(v) for v in _ZIGZAG_BREAKOUT])
    strategy = StrategyRow(code="mktint_test_strategy", name="mktint_test_strategy", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = Signal(
        strategy_id=strategy.id, asset_id=asset.id, ts=_NOW, direction="long", entry_price=75.0, stop_price=70.0,
        status="scored",
    )
    db_session.add(signal)
    db_session.commit()

    run_market_intelligence_cycle(db_session, top_n=20, now=_NOW)

    db_session.refresh(signal)
    assert signal.opportunity_type == BREAKOUT
    assert signal.fingerprint is not None
    assert signal.expires_at is not None


def test_run_market_intelligence_cycle_clusters_correlated_same_direction_signals(db_session):
    strategy = StrategyRow(code="mktint_cluster_strategy", name="mktint_cluster_strategy", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()

    asset_a = _asset(db_session, "MKTINT_CLUSTER_A")
    asset_b = _asset(db_session, "MKTINT_CLUSTER_B")
    _seed_candles(db_session, asset_a, [100.0] * 25)
    _seed_candles(db_session, asset_b, [100.0] * 25)
    db_session.add(
        CorrelationMatrixEntry(ts=_NOW, asset_id_a=asset_a.id, asset_id_b=asset_b.id, window_days=30, correlation=0.95)
    )
    for asset in (asset_a, asset_b):
        db_session.add(
            Signal(
                strategy_id=strategy.id, asset_id=asset.id, ts=_NOW, direction="long", entry_price=100.0,
                stop_price=95.0, status="scored",
            )
        )
    db_session.commit()

    run_market_intelligence_cycle(db_session, top_n=20, now=_NOW)

    clusters = db_session.query(OpportunityCluster).all()
    assert len(clusters) == 1
    assert set(clusters[0].asset_ids) == {asset_a.id, asset_b.id}


def test_run_market_intelligence_cycle_adds_watchlist_entry_on_anomaly(db_session):
    asset = _asset(db_session, "MKTINT_ANOMALY")
    closes = [100.0 + 0.01 * ((i % 2) * 2 - 1) for i in range(25)]
    closes.append(150.0)  # a huge outlier final bar -- a clear price_move anomaly
    _seed_candles(db_session, asset, closes)

    run_market_intelligence_cycle(db_session, top_n=20, now=_START + timedelta(minutes=26))

    assert db_session.query(Anomaly).filter(Anomaly.asset_id == asset.id).count() >= 1
    entry = db_session.query(WatchlistEntry).filter(WatchlistEntry.asset_id == asset.id).one()
    assert entry.status == "active"
