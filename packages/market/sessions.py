"""Market Sessions & Global Clock -- "PROMPT 11" §16-24.

Deliberately NOT persisted (see packages/shared/models.py's Prompt-11
section comment): a session state is a pure function of UTC time plus the
small, static per-exchange config below. Storing it would only ever be
stale between reads -- recomputing costs nothing.

UTC discipline (the spec's explicit requirement, §16): every public
function here takes/returns UTC-aware datetimes. Local (exchange) time
appears only inside `compute_session_state`, for exactly as long as it
takes to compare "now" against that exchange's local trading-hours config
via `zoneinfo` -- it is never compared, stored, or returned as the
authoritative clock.

Holidays are NOT modeled: a real per-exchange holiday calendar is out of
scope for a single-user paper-trading system (deliberate divergence from a
literal reading of §16-19; see docs/global-market-intelligence.md). A
holiday will misreport as OPEN. This does not create incorrect trading
behavior because the mock market data provider itself has no holiday
concept either -- it is an honest limitation of the data source, not a
bug introduced by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

# -- closed vocabulary -- "PROMPT 11" §16 --------------------------------
SESSION_OPEN = "open"
SESSION_PRE_MARKET = "pre_market"
SESSION_POST_MARKET = "post_market"
SESSION_CLOSED = "closed"
SESSION_24H = "24h"
SESSION_TRANSITION = "transition"
SESSION_UNKNOWN = "unknown"

SESSION_STATES = (
    SESSION_OPEN, SESSION_PRE_MARKET, SESSION_POST_MARKET, SESSION_CLOSED, SESSION_24H,
    SESSION_TRANSITION, SESSION_UNKNOWN,
)

# +/- this many minutes around an open/close boundary reports TRANSITION
# instead of flipping directly OPEN<->CLOSED -- avoids a scan cadence
# landing exactly on the boundary and reporting a state that's already
# stale by the time it's read.
TRANSITION_WINDOW_MINUTES = 5


@dataclass(frozen=True)
class SessionConfig:
    name: str
    tz: str  # IANA zone name
    open_time: time
    close_time: time
    pre_market_minutes: int = 0
    post_market_minutes: int = 0
    weekdays_open: tuple[int, ...] = (0, 1, 2, 3, 4)  # datetime.weekday(): Mon=0 .. Sun=6


# Named exchange sessions -- "PROMPT 11" §19: New York/London/Frankfurt/
# Tokyo/Hong Kong/Sydney (+ crypto's always-on session, handled separately
# below since it has no exchange hours at all).
NEW_YORK = SessionConfig(
    "new_york", "America/New_York", time(9, 30), time(16, 0),
    pre_market_minutes=330, post_market_minutes=240,  # 04:00 pre, 20:00 post
)
LONDON = SessionConfig("london", "Europe/London", time(8, 0), time(16, 30), pre_market_minutes=60)
FRANKFURT = SessionConfig("frankfurt", "Europe/Berlin", time(9, 0), time(17, 30), pre_market_minutes=60)
TOKYO = SessionConfig("tokyo", "Asia/Tokyo", time(9, 0), time(15, 0), pre_market_minutes=30)
HONG_KONG = SessionConfig("hong_kong", "Asia/Hong_Kong", time(9, 30), time(16, 0), pre_market_minutes=30)
SYDNEY = SessionConfig("sydney", "Australia/Sydney", time(10, 0), time(16, 0), pre_market_minutes=30)

NAMED_SESSIONS: tuple[SessionConfig, ...] = (NEW_YORK, LONDON, FRANKFURT, TOKYO, HONG_KONG, SYDNEY)

# Asset.exchange -> SessionConfig. An exchange not listed here is honestly
# reported SESSION_UNKNOWN rather than guessing hours for it.
EXCHANGE_SESSIONS: dict[str, SessionConfig] = {
    "NYSE": NEW_YORK,
    "NASDAQ": NEW_YORK,
    "LSE": LONDON,
    "XETRA": FRANKFURT,
    "FSE": FRANKFURT,
    "TSE": TOKYO,
    "HKEX": HONG_KONG,
    "ASX": SYDNEY,
}

# Named session-overlap pairs -- "PROMPT 11" §19's explicit examples
# (London/New York, Tokyo/London) plus the other two commonly-traded
# overlaps. A pair counts as "active" only when BOTH sides are OPEN or in
# TRANSITION (see GlobalMarketClock.snapshot).
KNOWN_OVERLAPS: tuple[tuple[str, str], ...] = (
    ("london", "new_york"),
    ("tokyo", "london"),
    ("sydney", "tokyo"),
    ("frankfurt", "new_york"),
)


@dataclass(frozen=True)
class SessionSnapshot:
    session: str
    state: str
    local_time: str  # HH:MM in the exchange's own timezone -- display only, never compared
    minutes_to_next_transition: int | None


def compute_session_state(config: SessionConfig, now_utc: datetime) -> SessionSnapshot:
    """Pure function: (static config, UTC instant) -> session state.

    No global-market knowledge here -- this is one exchange's local
    open/pre/post/closed logic. GlobalMarketClock composes N of these.
    """
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware (UTC discipline, PROMPT 11 §16)")

    local = now_utc.astimezone(ZoneInfo(config.tz))
    local_time_str = local.strftime("%H:%M")

    if local.weekday() not in config.weekdays_open:
        return SessionSnapshot(config.name, SESSION_CLOSED, local_time_str, None)

    open_dt = local.replace(hour=config.open_time.hour, minute=config.open_time.minute, second=0, microsecond=0)
    close_dt = local.replace(hour=config.close_time.hour, minute=config.close_time.minute, second=0, microsecond=0)
    pre_dt = open_dt - timedelta(minutes=config.pre_market_minutes)
    post_dt = close_dt + timedelta(minutes=config.post_market_minutes)
    transition = timedelta(minutes=TRANSITION_WINDOW_MINUTES)

    if abs(local - open_dt) <= transition or abs(local - close_dt) <= transition:
        state = SESSION_TRANSITION
    elif open_dt <= local < close_dt:
        state = SESSION_OPEN
    elif pre_dt <= local < open_dt:
        state = SESSION_PRE_MARKET
    elif close_dt <= local < post_dt:
        state = SESSION_POST_MARKET
    else:
        state = SESSION_CLOSED

    boundaries = sorted({pre_dt, open_dt, close_dt, post_dt})
    upcoming = [dt for dt in boundaries if dt > local]
    minutes_to_next = int((upcoming[0] - local).total_seconds() // 60) if upcoming else None

    return SessionSnapshot(config.name, state, local_time_str, minutes_to_next)


def _forex_session_state(now_utc: datetime) -> SessionSnapshot:
    """Forex has no single exchange -- it trades continuously from the
    Sydney open (Sun ~22:00 UTC) through the New York close (Fri ~22:00
    UTC), the union of the major-center sessions rather than any one of
    them. Approximated here with a fixed UTC weekend window rather than
    resolving all 4 underlying local opens/closes, since the practical
    effect (closed roughly Fri 22:00 UTC -> Sun 22:00 UTC) is the same.
    """
    weekday = now_utc.weekday()  # Mon=0 .. Sun=6
    hour = now_utc.hour
    weekend_closed = (
        weekday == 5  # all Saturday
        or (weekday == 6 and hour < 22)  # Sunday before 22:00 UTC
        or (weekday == 4 and hour >= 22)  # Friday from 22:00 UTC
    )
    state = SESSION_CLOSED if weekend_closed else SESSION_24H
    return SessionSnapshot("forex", state, now_utc.strftime("%H:%M"), None)


class MarketSessionEngine:
    """Resolves an asset's current session state from its asset_class +
    exchange -- "PROMPT 11" §16-18. Crypto is always 24h; forex follows the
    weekend-closed approximation above; equity/index/commodity assets
    defer to their exchange's SessionConfig.
    """

    def state_for(self, asset_class: str, exchange: str | None, now_utc: datetime | None = None) -> SessionSnapshot:
        now_utc = now_utc or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            raise ValueError("now_utc must be timezone-aware (UTC discipline, PROMPT 11 §16)")

        if asset_class == "crypto":
            return SessionSnapshot("crypto", SESSION_24H, now_utc.strftime("%H:%M"), None)
        if asset_class == "forex":
            return _forex_session_state(now_utc)

        config = EXCHANGE_SESSIONS.get((exchange or "").upper())
        if config is None:
            return SessionSnapshot(exchange or "unknown", SESSION_UNKNOWN, now_utc.strftime("%H:%M"), None)
        return compute_session_state(config, now_utc)


@dataclass(frozen=True)
class GlobalMarketSnapshot:
    ts: datetime
    sessions: tuple[SessionSnapshot, ...]
    active_overlaps: tuple[tuple[str, str], ...]


class GlobalMarketClock:
    """Monitors the 6 named exchange sessions and flags session-overlap
    windows -- "PROMPT 11" §19-20. Overlaps are evidence for
    session-specific strategy compatibility, not enforced by this module
    (it only reports which windows are active).
    """

    def __init__(self, sessions: tuple[SessionConfig, ...] = NAMED_SESSIONS):
        self._sessions = sessions

    def snapshot(self, now_utc: datetime | None = None) -> GlobalMarketSnapshot:
        now_utc = now_utc or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            raise ValueError("now_utc must be timezone-aware (UTC discipline, PROMPT 11 §16)")

        snapshots = tuple(compute_session_state(cfg, now_utc) for cfg in self._sessions)
        active = {s.session for s in snapshots if s.state in (SESSION_OPEN, SESSION_TRANSITION)}
        overlaps = tuple(pair for pair in KNOWN_OVERLAPS if pair[0] in active and pair[1] in active)
        return GlobalMarketSnapshot(ts=now_utc, sessions=snapshots, active_overlaps=overlaps)
