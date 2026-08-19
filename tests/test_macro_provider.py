from datetime import datetime, timedelta, timezone

from packages.data.connectors.macro.mock import MockMacroCalendarProvider


def test_deterministic_across_repeated_calls():
    provider = MockMacroCalendarProvider()
    now = datetime.now(timezone.utc)
    start, end = now - timedelta(days=7), now + timedelta(days=14)
    first = provider.get_events(start, end)
    second = provider.get_events(start, end)
    assert first == second
    assert len(first) > 0


def test_future_events_never_have_an_actual_value():
    provider = MockMacroCalendarProvider()
    now = datetime.now(timezone.utc)
    events = provider.get_events(now, now + timedelta(days=30))
    future_events = [e for e in events if e.scheduled_at > now]
    assert future_events  # sanity: the window does contain future events
    assert all(e.actual is None for e in future_events)


def test_past_events_have_an_actual_value():
    provider = MockMacroCalendarProvider()
    now = datetime.now(timezone.utc)
    events = provider.get_events(now - timedelta(days=60), now - timedelta(minutes=1))
    assert events  # sanity: the window does contain past events
    assert all(e.actual is not None for e in events)


def test_events_are_sorted_by_scheduled_time():
    provider = MockMacroCalendarProvider()
    now = datetime.now(timezone.utc)
    events = provider.get_events(now - timedelta(days=7), now + timedelta(days=14))
    scheduled = [e.scheduled_at for e in events]
    assert scheduled == sorted(scheduled)
