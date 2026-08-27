"""CentralEventBus -- "PROMPT 14" §71-73.

No pytest-asyncio dependency needed: asyncio.Queue() (Python 3.10+) doesn't
bind to a running loop at construction, so CentralEventBus.subscribe() works
fine called from a plain sync test; asyncio.run() drives the one-shot
awaits, matching this project's "no new test infra unless genuinely needed"
discipline.
"""
from __future__ import annotations

import asyncio

import pytest

from packages.events.bus import _QUEUE_MAXSIZE, CentralEventBus, Event
from packages.events.channels import CHANNELS


def test_event_to_dict_has_the_exact_schema_fields():
    event = Event(event_type="x", source="s", channel="system", payload={"a": 1}, severity="warning", correlation_id="signal:1")
    d = event.to_dict()
    assert set(d.keys()) == {"event_id", "event_type", "source", "channel", "timestamp", "payload", "severity", "correlation_id"}
    assert d["correlation_id"] == "signal:1"


def test_event_defaults_to_info_severity_and_no_correlation_id():
    event = Event(event_type="x", source="s", channel="system")
    assert event.severity == "info"
    assert event.correlation_id is None
    assert event.event_id  # a real uuid, not empty


def test_subscribe_rejects_unknown_channel():
    bus = CentralEventBus()
    with pytest.raises(ValueError):
        bus.subscribe("not_a_real_channel")


def test_publish_rejects_unknown_channel():
    bus = CentralEventBus()
    with pytest.raises(ValueError):
        bus.publish(Event(event_type="x", source="s", channel="not_a_real_channel"))


def test_publish_delivers_to_a_subscribed_queue():
    bus = CentralEventBus()
    queue = bus.subscribe("system")
    bus.publish(Event(event_type="heartbeat", source="tailer", channel="system"))
    event = asyncio.run(asyncio.wait_for(queue.get(), timeout=1))
    assert event.event_type == "heartbeat"


def test_publish_never_delivers_to_a_different_channels_subscriber():
    bus = CentralEventBus()
    queue = bus.subscribe("risk")
    bus.publish(Event(event_type="x", source="s", channel="system"))
    assert queue.empty()


def test_unsubscribe_stops_delivery():
    bus = CentralEventBus()
    queue = bus.subscribe("alerts")
    bus.unsubscribe("alerts", queue)
    bus.publish(Event(event_type="x", source="s", channel="alerts"))
    assert queue.empty()


def test_two_subscribers_on_the_same_channel_both_receive_the_event():
    bus = CentralEventBus()
    q1 = bus.subscribe("execution")
    q2 = bus.subscribe("execution")
    bus.publish(Event(event_type="order_filled", source="trading_events", channel="execution"))
    e1 = asyncio.run(asyncio.wait_for(q1.get(), timeout=1))
    e2 = asyncio.run(asyncio.wait_for(q2.get(), timeout=1))
    assert e1.event_id == e2.event_id


def test_full_queue_drops_oldest_and_counts_the_drop():
    """§102 -- a slow/disconnected subscriber never blocks every other
    subscriber, and the drop is counted (never silent)."""
    bus = CentralEventBus()
    queue = bus.subscribe("events")
    for i in range(_QUEUE_MAXSIZE + 5):
        bus.publish(Event(event_type=f"e{i}", source="s", channel="events"))

    assert bus.dropped_count >= 5
    assert queue.qsize() == _QUEUE_MAXSIZE

    last = None
    while not queue.empty():
        last = queue.get_nowait()
    assert last is not None
    assert last.event_type == f"e{_QUEUE_MAXSIZE + 4}"  # the most recent event was never dropped


def test_subscriber_count_and_total_subscribers():
    bus = CentralEventBus()
    bus.subscribe("system")
    bus.subscribe("risk")
    bus.subscribe("risk")
    assert bus.subscriber_count("system") == 1
    assert bus.subscriber_count("risk") == 2
    assert bus.total_subscribers() == 3


def test_every_channel_is_independently_subscribable():
    bus = CentralEventBus()
    for channel in CHANNELS:
        bus.subscribe(channel)
    assert bus.total_subscribers() == len(CHANNELS)
