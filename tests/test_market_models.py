"""Model/schema layer for "PROMPT 11" (global market intelligence) — asset
metadata, signal opportunity fields, and the 4 new tables. Behavioral
coverage for the engines that populate these tables lives in their own
test files (tests/test_market_*.py); this file only proves the schema
itself round-trips and enforces its constraints.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from packages.shared.models import (
    Anomaly,
    Asset,
    OpportunityCluster,
    Signal,
    StrategyRow,
    VolatilityEvent,
    WatchlistEntry,
)


def _asset(db_session, symbol: str, **overrides) -> Asset:
    asset = Asset(symbol=symbol, asset_class="crypto", **overrides)
    db_session.add(asset)
    db_session.commit()
    return asset


def test_asset_defaults_to_active_status_and_keeps_is_active(db_session):
    asset = _asset(db_session, "MKT_ASSET_DEFAULT")
    assert asset.status == "active"
    assert asset.is_active is True  # untouched derived convenience column


def test_asset_accepts_full_metadata(db_session):
    asset = _asset(
        db_session,
        "MKT_ASSET_META",
        name="Market Asset Meta",
        currency="USD",
        country="US",
        sector="Technology",
        industry="Software",
        timezone="America/New_York",
        trading_hours={"open": "09:30", "close": "16:00"},
        liquidity_score=82.5,
        data_quality_score=91.0,
    )
    assert asset.trading_hours == {"open": "09:30", "close": "16:00"}
    assert asset.liquidity_score == 82.5


def test_asset_status_check_constraint_rejects_unknown_value(db_session):
    asset = Asset(symbol="MKT_ASSET_BADSTATUS", asset_class="crypto", status="not_a_real_status")
    db_session.add(asset)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_asset_class_check_constraint_now_accepts_architecture_ready_classes(db_session):
    for cls in ("etf", "future", "bond", "option"):
        asset = Asset(symbol=f"MKT_ASSET_{cls.upper()}", asset_class=cls)
        db_session.add(asset)
    db_session.commit()  # no IntegrityError -- widened CHECK accepts them


def test_asset_class_check_constraint_still_rejects_unknown_class(db_session):
    asset = Asset(symbol="MKT_ASSET_FAKECLASS", asset_class="not_a_real_class")
    db_session.add(asset)
    with pytest.raises(IntegrityError):
        db_session.commit()


def _signal(db_session, **overrides) -> Signal:
    strategy = StrategyRow(code="mkt_test_strategy", name="mkt_test_strategy", family="test", version="1.0")
    asset = _asset(db_session, overrides.pop("symbol", "MKT_SIGNAL_ASSET"))
    signal = Signal(
        strategy_id=None, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0, **overrides
    )
    db_session.add(strategy)
    db_session.commit()
    signal.strategy_id = strategy.id
    db_session.add(signal)
    db_session.commit()
    return signal


def test_signal_opportunity_fields_round_trip(db_session):
    expires = datetime.now(timezone.utc) + timedelta(hours=4)
    signal = _signal(
        db_session,
        symbol="MKT_SIGNAL_ROUNDTRIP",
        opportunity_type="breakout",
        fingerprint="MKT_SIGNAL_ROUNDTRIP:long:breakout:100.0",
        expires_at=expires,
    )
    db_session.refresh(signal)
    assert signal.opportunity_type == "breakout"
    assert signal.fingerprint.startswith("MKT_SIGNAL_ROUNDTRIP")
    assert signal.expires_at is not None


def test_signal_opportunity_type_check_constraint_rejects_unknown_value(db_session):
    with pytest.raises(IntegrityError):
        _signal(db_session, symbol="MKT_SIGNAL_BADTYPE", opportunity_type="not_a_real_type")


def test_signal_status_check_constraint_now_accepts_invalidated(db_session):
    signal = _signal(db_session, symbol="MKT_SIGNAL_INVALIDATED", status="invalidated")
    assert signal.status == "invalidated"


def test_opportunity_cluster_round_trip_and_direction_constraint(db_session):
    cluster = OpportunityCluster(
        signal_ids=[1, 2, 3],
        asset_ids=[10, 20, 30],
        direction="long",
        factor="crypto_beta",
        avg_correlation=0.87,
        combined_risk=0.42,
        ranking_penalty=0.15,
    )
    db_session.add(cluster)
    db_session.commit()
    assert cluster.id is not None

    bad = OpportunityCluster(
        signal_ids=[1], asset_ids=[10], direction="sideways", avg_correlation=0.5, combined_risk=0.1,
        ranking_penalty=0.0,
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_anomaly_round_trip_and_score_range_constraint(db_session):
    asset = _asset(db_session, "MKT_ANOMALY_ASSET")
    anomaly = Anomaly(
        asset_id=asset.id, anomaly_type="price_move", score=72.0, evidence={"z_score": 4.1}, reviewed=False,
    )
    db_session.add(anomaly)
    db_session.commit()
    assert anomaly.reviewed is False

    out_of_range = Anomaly(asset_id=asset.id, anomaly_type="price_move", score=150.0, evidence={})
    db_session.add(out_of_range)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_volatility_event_round_trip_and_constraints(db_session):
    asset = _asset(db_session, "MKT_VOLEVENT_ASSET")
    event = VolatilityEvent(
        asset_id=asset.id, timeframe="1h", event_type="expansion", realized_vol=0.032, percentile=88.0,
        regime="high",
    )
    db_session.add(event)
    db_session.commit()
    assert event.regime == "high"

    bad = VolatilityEvent(
        asset_id=asset.id, timeframe="1h", event_type="not_a_real_event", realized_vol=0.01, percentile=10.0,
        regime="low",
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_watchlist_entry_is_unique_per_asset(db_session):
    asset = _asset(db_session, "MKT_WATCHLIST_ASSET")
    entry = WatchlistEntry(asset_id=asset.id, reason="anomaly", status="active")
    db_session.add(entry)
    db_session.commit()

    duplicate = WatchlistEntry(asset_id=asset.id, reason="news", status="active")
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_watchlist_entry_removal_reason_constraint(db_session):
    asset = _asset(db_session, "MKT_WATCHLIST_REMOVAL")
    entry = WatchlistEntry(
        asset_id=asset.id, reason="volume", status="removed", removal_reason="liquidity_deterioration",
    )
    db_session.add(entry)
    db_session.commit()
    assert entry.removal_reason == "liquidity_deterioration"
