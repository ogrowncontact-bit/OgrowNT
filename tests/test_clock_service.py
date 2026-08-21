"""packages/execution/clock.py -- "PROMPT 13" §55-56."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.execution.clock import ClockService

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_drift_within_tolerance_is_ok():
    result = ClockService().check_drift(_NOW - timedelta(seconds=1), now=_NOW, max_drift_seconds=5.0)
    assert result.within_tolerance is True


def test_drift_exceeding_tolerance_is_flagged():
    result = ClockService().check_drift(_NOW - timedelta(seconds=30), now=_NOW, max_drift_seconds=5.0)
    assert result.within_tolerance is False
    assert result.reasons


def test_drift_is_symmetric_a_fast_clock_is_also_flagged():
    result = ClockService().check_drift(_NOW + timedelta(seconds=30), now=_NOW, max_drift_seconds=5.0)
    assert result.within_tolerance is False


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        ClockService().check_drift(datetime(2026, 1, 1), now=_NOW)


def test_validate_timestamp_is_a_boolean_convenience_wrapper():
    assert ClockService().validate_timestamp(_NOW, now=_NOW) is True
    assert ClockService().validate_timestamp(_NOW - timedelta(hours=1), now=_NOW, max_drift_seconds=5.0) is False
