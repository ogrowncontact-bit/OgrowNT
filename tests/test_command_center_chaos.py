"""Chaos testing -- "PROMPT 14" §102, §124-129, §131-132: event bus flood
resilience, tail-loop DB-outage resilience, and self-diagnostic behavior
when the database itself is the thing that's broken. Same "simulate the
failure mode directly, confirm the system degrades safely rather than
crashing or corrupting state" discipline as tests/test_execution_chaos.py
("PROMPT 13" §100-101).

The event bus's own queue-overflow/drop-oldest behavior is already directly
unit-tested in tests/test_events_bus.py::test_full_queue_drops_oldest_and_counts_the_drop
-- this file does not repeat that at the single-subscriber level. It covers
scenarios that file doesn't: multiple channels under simultaneous load, the
real DB-tail loop surviving a bad iteration, and self-diagnostic staying
honest under a genuinely broken database connection (not just an empty one).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import apps.api.realtime as realtime
from packages.events.bus import CentralEventBus, Event
from packages.shared.settings import get_settings
from packages.system.diagnostics import run_self_diagnostic


@pytest.fixture()
def fast_poll_interval():
    """apps/api/realtime._tail_loop's poll cadence comes from the cached
    Settings singleton (packages.shared.settings.get_settings(), @lru_cache)
    -- mutating that instance's field directly (pydantic BaseSettings models
    are mutable by default) is the only way to speed up a chaos test that
    needs several real tail-loop ticks without waiting 2s * N."""
    settings = get_settings()
    original = settings.event_poll_interval_seconds
    settings.event_poll_interval_seconds = 0.02
    try:
        yield
    finally:
        settings.event_poll_interval_seconds = original


# 1. A flood of publishes on ONE channel with a subscriber that never drains
#    must never block or slow delivery on a completely different channel --
#    a runaway producer on "market" must not starve a healthy "alerts"
#    subscriber sharing the same bus instance.
def test_flood_on_one_channel_never_starves_delivery_on_another_channel():
    bus = CentralEventBus()
    flooded_queue = bus.subscribe("market")  # deliberately never drained
    healthy_queue = bus.subscribe("alerts")

    for i in range(2_000):
        bus.publish(Event(event_type=f"tick_{i}", source="chaos-test", channel="market"))

    bus.publish(Event(event_type="incident_created", source="chaos-test", channel="alerts", payload={"marker": "expected"}))

    assert bus.dropped_count > 0  # the flood genuinely overran the bounded queue
    delivered = asyncio.run(asyncio.wait_for(healthy_queue.get(), timeout=1))
    assert delivered.payload.get("marker") == "expected"
    assert flooded_queue.qsize() > 0  # the flooded subscriber still has SOMETHING, not starved to zero either


# 2. The real DB-tail loop must survive one bad iteration (a transient DB
#    blip mid-tick) and keep publishing heartbeats on the next tick, rather
#    than the whole background task dying silently and the dashboard going
#    dark with no further explanation.
def test_tail_loop_survives_one_bad_iteration_and_keeps_publishing_afterward(monkeypatch, fast_poll_interval):
    real_tail_new_events = realtime.tail_new_events
    call_count = 0

    def _flaky_once(db, *, since_trading_event_id, since_alert_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated transient DB blip")
        return real_tail_new_events(db, since_trading_event_id=since_trading_event_id, since_alert_id=since_alert_id)

    monkeypatch.setattr(realtime, "tail_new_events", _flaky_once)

    async def _main():
        bus = CentralEventBus()
        app_stub = SimpleNamespace(state=SimpleNamespace(bus=bus))
        queue = bus.subscribe("system")
        task = asyncio.create_task(realtime._tail_loop(app_stub))
        try:
            return await asyncio.wait_for(queue.get(), timeout=5)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    event = asyncio.run(_main())
    assert event.event_type == "heartbeat"
    assert call_count >= 2  # the bad tick happened AND at least one good tick followed it


# 3. The tail loop must survive many consecutive bad iterations too, not
#    just a single blip -- an outage that lasts several ticks must not wedge
#    the background task into a dead state it never recovers from once the
#    DB comes back.
def test_tail_loop_survives_a_sustained_outage_and_recovers_once_it_ends(monkeypatch, fast_poll_interval):
    real_tail_new_events = realtime.tail_new_events
    call_count = 0
    OUTAGE_TICKS = 5

    def _flaky(db, *, since_trading_event_id, since_alert_id):
        nonlocal call_count
        call_count += 1
        if call_count <= OUTAGE_TICKS:
            raise ConnectionError("simulated sustained DB outage")
        return real_tail_new_events(db, since_trading_event_id=since_trading_event_id, since_alert_id=since_alert_id)

    monkeypatch.setattr(realtime, "tail_new_events", _flaky)

    async def _main():
        bus = CentralEventBus()
        app_stub = SimpleNamespace(state=SimpleNamespace(bus=bus))
        queue = bus.subscribe("system")
        task = asyncio.create_task(realtime._tail_loop(app_stub))
        try:
            return await asyncio.wait_for(queue.get(), timeout=10)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    event = asyncio.run(_main())
    assert event.event_type == "heartbeat"
    assert call_count > OUTAGE_TICKS


# 4. Self-diagnostic must stay honest -- not crash -- when the database
#    connection itself dies partway through the check sequence, which is
#    exactly the moment an operator most needs an honest report rather than
#    an unhandled exception. Reproduces a genuine gap found while writing
#    this battery: only the first ("database") check was exception-guarded;
#    packages/system/diagnostics.py now guards every DB-touching check
#    independently, matching the module's own "never crashes" docstring.
def test_self_diagnostic_survives_the_database_connection_dying_mid_check(db_session):
    db_session.connection().connection.close()
    report = run_self_diagnostic(db_session)
    assert report.ok is False
    names = {c.name for c in report.checks}
    assert names == {"database", "data", "workers", "broker", "event_bus"}
    for check in report.checks:
        if check.name != "event_bus":
            assert check.ok is False
