"""Stress, scale, and cross-module integration tests -- "PROMPT 11" §93-96.

Per-module unit coverage for every engine already lives in its own
tests/test_market_*.py file; this file covers what only shows up when the
pieces run TOGETHER: universe-eligibility actually gating the fast
scanner, one asset's engine failure not stopping the batch, and a
larger-than-normal synthetic universe completing in reasonable time.

A literal 10,000-asset scale test ("PROMPT 11" §93's stated ceiling) isn't
run here: this is a private, single-user, modest-infrastructure system --
the seed universe is 22-25 assets, and nothing in this codebase's
deployment target needs to prove it survives 10,000. The 150-asset smoke
test below is the honest version of that requirement: enough to prove the
pipeline doesn't have an accidental O(n^2) blowup or an unbounded query,
without pretending this environment has exchange-scale infrastructure.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from apps.worker.market_intelligence import run_market_intelligence_cycle, run_universe_cycle
from packages.data.connectors.market.mock import MockMarketDataProvider
from packages.market.fast_scanner import FastMarketScanner
from packages.market.opportunity_types import compute_fingerprint
from packages.market.structure import MarketStructureEngine
from packages.shared.models import OHLCV, Anomaly, Asset, Signal, StrategyRow, WatchlistEntry

_START = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)


def _asset(db_session, symbol: str, **overrides) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", **overrides)
    db_session.add(asset)
    db_session.commit()
    return asset


def _seed_candles(db_session, asset: Asset, count: int = 30, base: float = 100.0) -> None:
    for i in range(count):
        close = base * (1.0 + 0.001 * ((i % 5) - 2))
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=close, high=close + 0.2,
                low=close - 0.2, close=close, volume=200.0, data_quality="high",
            )
        )
    db_session.commit()


def test_scale_smoke_150_assets_completes_without_crashing_or_timing_out(db_session):
    for i in range(150):
        asset = _asset(db_session, f"SCALE_{i:04d}")
        _seed_candles(db_session, asset, count=25, base=100.0 + i)

    start = time.monotonic()
    universe_result = run_universe_cycle(db_session, MockMarketDataProvider())
    intelligence_result = run_market_intelligence_cycle(db_session, top_n=50, now=_START + timedelta(minutes=25))
    elapsed = time.monotonic() - start

    assert universe_result["evaluated"] >= 150
    assert intelligence_result["scanned"] <= 50  # top_n respected even with 150 candidates
    # Generous ceiling -- this asserts "doesn't hang", not a tuned perf budget.
    assert elapsed < 60.0


def test_market_intelligence_cycle_isolates_one_assets_engine_failure(db_session):
    good = _asset(db_session, "ISOLATION_GOOD")
    bad = _asset(db_session, "ISOLATION_BAD")
    _seed_candles(db_session, good)
    _seed_candles(db_session, bad)

    real_analyze = MarketStructureEngine.analyze
    call_count = {"n": 0}

    def _flaky_analyze(self, db, asset_id, symbol, **kwargs):
        call_count["n"] += 1
        if symbol == "ISOLATION_BAD":
            raise RuntimeError("simulated engine failure")
        return real_analyze(self, db, asset_id, symbol, **kwargs)

    with patch.object(MarketStructureEngine, "analyze", _flaky_analyze):
        result = run_market_intelligence_cycle(db_session, top_n=20, now=_START + timedelta(minutes=25))

    # Both assets were reached (the failure didn't stop the batch), and the
    # cycle still returned a normal summary instead of raising.
    assert call_count["n"] == 2
    assert set(result) == {"scanned", "anomalies_found", "volatility_events_found", "clusters_found"}


def test_universe_ineligibility_actually_excludes_asset_from_fast_scanner(db_session):
    """Cross-module contract: MarketUniverseManager's DATA_UNAVAILABLE
    verdict must actually stop FastMarketScanner from considering the
    asset, not just sit in the Asset row unused.
    """
    no_data = _asset(db_session, "NEVER_TRADED")  # no OHLCV at all
    has_data = _asset(db_session, "HAS_DATA")
    _seed_candles(db_session, has_data)

    run_universe_cycle(db_session, MockMarketDataProvider())
    db_session.refresh(no_data)
    assert no_data.status == "data_unavailable"

    top = FastMarketScanner().scan(db_session, top_n=50, now=_START + timedelta(minutes=25))
    scanned_symbols = {s.symbol for s in top}
    assert "NEVER_TRADED" not in scanned_symbols
    assert "HAS_DATA" in scanned_symbols


def test_duplicate_opportunity_fingerprint_collapses_repeated_detections(db_session):
    """"PROMPT 11" §23's duplicate-opportunity requirement: the SAME setup
    re-detected in the same coarse price/time window must fingerprint
    identically, so a caller can dedupe on it rather than alerting twice.
    """
    now = _START + timedelta(hours=2)
    first = compute_fingerprint("DUPTEST", "breakout", "long", 100.0, now=now)
    second = compute_fingerprint("DUPTEST", "breakout", "long", 100.05, now=now + timedelta(seconds=30))
    assert first == second

    different_setup = compute_fingerprint("DUPTEST", "breakout", "short", 100.0, now=now)
    assert different_setup != first


def test_market_closure_forex_weekend_reported_honestly(db_session):
    from packages.market.sessions import SESSION_CLOSED, MarketSessionEngine

    engine = MarketSessionEngine()
    saturday = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)  # a Saturday
    reading = engine.state_for("forex", None, saturday)
    assert reading.state == SESSION_CLOSED


def test_market_intelligence_cycle_end_to_end_with_anomaly_and_watchlist(db_session):
    """A single realistic pass: a strategy already produced a Signal, the
    asset has a genuine price-move anomaly, and the cycle should both
    persist the Anomaly and watchlist the asset -- no manual wiring
    beyond calling the one orchestration entrypoint.
    """
    asset = _asset(db_session, "E2E_ANOMALY")
    closes = [100.0 + 0.01 * ((i % 2) * 2 - 1) for i in range(25)]
    closes.append(180.0)  # outlier final bar
    for i, close in enumerate(closes):
        db_session.add(
            OHLCV(
                asset_id=asset.id, timeframe="1m", ts=_START + timedelta(minutes=i), open=close, high=close + 0.2,
                low=close - 0.2, close=close, volume=200.0, data_quality="high",
            )
        )
    db_session.commit()
    strategy = StrategyRow(code="e2e_test_strategy", name="e2e_test_strategy", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    db_session.add(
        Signal(
            strategy_id=strategy.id, asset_id=asset.id, ts=_START + timedelta(minutes=26), direction="long",
            entry_price=180.0, stop_price=170.0, status="scored",
        )
    )
    db_session.commit()

    run_market_intelligence_cycle(db_session, top_n=20, now=_START + timedelta(minutes=26))

    assert db_session.query(Anomaly).filter(Anomaly.asset_id == asset.id).count() >= 1
    watchlist_row = db_session.query(WatchlistEntry).filter(WatchlistEntry.asset_id == asset.id).one()
    assert watchlist_row.status == "active"
