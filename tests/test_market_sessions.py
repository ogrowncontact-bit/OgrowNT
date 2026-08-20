"""Market Sessions & Global Clock -- "PROMPT 11" §16-24."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.market.sessions import (
    NEW_YORK,
    SESSION_24H,
    SESSION_CLOSED,
    SESSION_OPEN,
    SESSION_POST_MARKET,
    SESSION_PRE_MARKET,
    SESSION_TRANSITION,
    SESSION_UNKNOWN,
    GlobalMarketClock,
    MarketSessionEngine,
    compute_session_state,
)


def _utc(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def test_compute_session_state_requires_timezone_aware_input():
    with pytest.raises(ValueError):
        compute_session_state(NEW_YORK, datetime(2026, 7, 15, 10, 0))  # naive


def test_compute_session_state_pre_market():
    snap = compute_session_state(NEW_YORK, _utc(2026, 7, 15, 10, 0))  # 06:00 NY local
    assert snap.state == SESSION_PRE_MARKET


def test_compute_session_state_open():
    snap = compute_session_state(NEW_YORK, _utc(2026, 7, 15, 16, 0))  # 12:00 NY local
    assert snap.state == SESSION_OPEN
    assert snap.local_time == "12:00"


def test_compute_session_state_post_market():
    snap = compute_session_state(NEW_YORK, _utc(2026, 7, 15, 22, 0))  # 18:00 NY local
    assert snap.state == SESSION_POST_MARKET


def test_compute_session_state_closed_overnight():
    snap = compute_session_state(NEW_YORK, _utc(2026, 7, 16, 2, 0))  # 22:00 NY local
    assert snap.state == SESSION_CLOSED


def test_compute_session_state_weekend_closed():
    # 2026-07-18 is a Saturday
    snap = compute_session_state(NEW_YORK, _utc(2026, 7, 18, 16, 0))
    assert snap.state == SESSION_CLOSED


def test_compute_session_state_transition_at_open_boundary():
    snap = compute_session_state(NEW_YORK, _utc(2026, 7, 15, 13, 30))  # exactly 09:30 NY local
    assert snap.state == SESSION_TRANSITION
    assert snap.minutes_to_next_transition is not None


def test_market_session_engine_crypto_is_always_24h():
    engine = MarketSessionEngine()
    snap = engine.state_for("crypto", None, _utc(2026, 7, 18, 3, 0))  # a Saturday night
    assert snap.state == SESSION_24H


def test_market_session_engine_forex_weekday_is_24h():
    engine = MarketSessionEngine()
    snap = engine.state_for("forex", None, _utc(2026, 7, 15, 14, 0))  # Wednesday
    assert snap.state == SESSION_24H


def test_market_session_engine_forex_saturday_is_closed():
    engine = MarketSessionEngine()
    snap = engine.state_for("forex", None, _utc(2026, 7, 18, 14, 0))  # Saturday
    assert snap.state == SESSION_CLOSED


def test_market_session_engine_known_exchange_resolves():
    engine = MarketSessionEngine()
    snap = engine.state_for("equity", "NYSE", _utc(2026, 7, 15, 16, 0))
    assert snap.session == "new_york"
    assert snap.state == SESSION_OPEN


def test_market_session_engine_unknown_exchange_is_honest_not_fabricated():
    engine = MarketSessionEngine()
    snap = engine.state_for("equity", "SOME_MADE_UP_EXCHANGE", _utc(2026, 7, 15, 16, 0))
    assert snap.state == SESSION_UNKNOWN


def test_market_session_engine_rejects_naive_datetime():
    engine = MarketSessionEngine()
    with pytest.raises(ValueError):
        engine.state_for("crypto", None, datetime(2026, 7, 15, 10, 0))


def test_global_market_clock_detects_london_new_york_overlap():
    clock = GlobalMarketClock()
    snap = clock.snapshot(_utc(2026, 7, 15, 14, 0))  # NY 10:00, London 15:00 -- both open
    assert ("london", "new_york") in snap.active_overlaps


def test_global_market_clock_reports_no_overlaps_in_the_dead_zone():
    clock = GlobalMarketClock()
    snap = clock.snapshot(_utc(2026, 7, 15, 1, 0))  # NY post-close, London pre-open
    assert ("london", "new_york") not in snap.active_overlaps


def test_global_market_clock_rejects_naive_datetime():
    clock = GlobalMarketClock()
    with pytest.raises(ValueError):
        clock.snapshot(datetime(2026, 7, 15, 10, 0))
