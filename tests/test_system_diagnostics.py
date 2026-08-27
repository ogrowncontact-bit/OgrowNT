"""packages/system/diagnostics.py -- "PROMPT 14" §124-129."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.events.bus import CentralEventBus
from packages.shared.models import OHLCV, Asset, Broker, SystemState
from packages.shared.worker_health import record_heartbeat
from packages.system.diagnostics import run_self_diagnostic


def _named_check(report, name):
    return next(c for c in report.checks if c.name == name)


def test_database_check_passes_against_a_real_connection(db_session):
    report = run_self_diagnostic(db_session)
    assert _named_check(report, "database").ok is True


def test_no_ohlcv_at_all_fails_the_data_check(db_session):
    report = run_self_diagnostic(db_session)
    assert _named_check(report, "data").ok is False


def test_fresh_ohlcv_passes_the_data_check(db_session):
    asset = Asset(symbol="DIAGFRESH", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=1, high=1, low=1, close=1, volume=1))
    db_session.commit()
    report = run_self_diagnostic(db_session)
    assert _named_check(report, "data").ok is True


def test_stale_ohlcv_fails_the_data_check(db_session):
    asset = Asset(symbol="DIAGSTALE", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc) - timedelta(hours=2), open=1, high=1, low=1, close=1, volume=1))
    db_session.commit()
    report = run_self_diagnostic(db_session)
    assert _named_check(report, "data").ok is False


def test_no_heartbeat_fails_the_workers_check(db_session):
    report = run_self_diagnostic(db_session)
    assert _named_check(report, "workers").ok is False


def test_fresh_heartbeat_passes_the_workers_check(db_session):
    record_heartbeat(db_session)
    report = run_self_diagnostic(db_session)
    assert _named_check(report, "workers").ok is True


def test_no_active_broker_fails_the_broker_check(db_session):
    report = run_self_diagnostic(db_session)
    assert _named_check(report, "broker").ok is False


def test_an_active_broker_passes_the_broker_check(db_session):
    db_session.add(Broker(name="paper", kind="paper", status="active", is_default=True))
    db_session.commit()
    report = run_self_diagnostic(db_session)
    assert _named_check(report, "broker").ok is True


def test_event_bus_check_reflects_whether_a_bus_was_supplied(db_session):
    without_bus = run_self_diagnostic(db_session, bus=None)
    assert _named_check(without_bus, "event_bus").ok is False

    with_bus = run_self_diagnostic(db_session, bus=CentralEventBus())
    assert _named_check(with_bus, "event_bus").ok is True


def test_report_ok_is_false_if_any_single_check_fails(db_session):
    # Fresh DB: data/workers/broker all honestly fail by default.
    report = run_self_diagnostic(db_session)
    assert report.ok is False


def test_report_ok_is_true_only_when_every_check_passes(db_session):
    db_session.add(SystemState(id=True))
    asset = Asset(symbol="DIAGALLGOOD", asset_class="crypto", is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=datetime.now(timezone.utc), open=1, high=1, low=1, close=1, volume=1))
    db_session.add(Broker(name="paper", kind="paper", status="active", is_default=True))
    record_heartbeat(db_session)
    db_session.commit()
    report = run_self_diagnostic(db_session, bus=CentralEventBus())
    assert report.ok is True
