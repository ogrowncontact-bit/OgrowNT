"""Mock macro calendar provider — Prompt 6 default (MACRO_CALENDAR_PROVIDER=mock).

THIS IS NOT A REAL ECONOMIC CALENDAR. Every event below is a synthetic,
deterministic recurrence of a real-world event *type* (CPI, NFP, rate
decisions, ...), not a real scheduled release. Before any live capital, or
before Prompt 6's MacroCalendarWorker acts on anything real, replace this
with a real adapter behind the same MacroCalendarProvider protocol:

    TODO(real-macro-data): implement a provider against a real economic
    calendar API (e.g. Trading Economics, FRED release calendar) and switch
    MACRO_CALENDAR_PROVIDER away from "mock" in production config.

Determinism (same idiom as MockNewsProvider/MockMarketDataProvider): each
template recurs on a fixed cycle derived from its own name, so calling
get_events() repeatedly for the same window always returns the same
events with the same forecast/previous/actual — a real calendar doesn't
change every time you look at it either. `actual` is only ever populated
for an occurrence whose scheduled_at is at or before "now" — never for a
future one, matching Prompt 6 §16's "não assumir a direção do mercado" in
spirit: this provider won't even pretend a number exists before its time.
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone

from packages.data.connectors.macro.base import MacroEventItem

# (event, country, currency, importance, baseline_forecast, baseline_previous,
#  surprise_std, cycle_days) — cycle_days is how often this recurs; a real
# calendar's actual cadence (e.g. NFP is monthly) doesn't matter for a mock,
# only that occurrences are stable and reasonably frequent for testing.
_TEMPLATES: list[tuple[str, str, str, str, float, float, float, int]] = [
    ("CPI y/y", "US", "USD", "high", 3.0, 2.9, 0.3, 30),
    ("Core CPI y/y", "US", "USD", "high", 3.2, 3.1, 0.2, 30),
    ("Non-Farm Payrolls", "US", "USD", "critical", 180.0, 175.0, 60.0, 30),
    ("Fed Interest Rate Decision", "US", "USD", "critical", 5.25, 5.25, 0.25, 42),
    ("GDP q/q", "US", "USD", "high", 2.1, 2.0, 0.4, 90),
    ("ECB Interest Rate Decision", "EU", "EUR", "critical", 4.0, 4.0, 0.25, 42),
    ("Eurozone CPI y/y", "EU", "EUR", "high", 2.6, 2.5, 0.3, 30),
    ("PMI Manufacturing", "US", "USD", "medium", 50.5, 50.0, 1.5, 30),
    ("Retail Sales m/m", "US", "USD", "medium", 0.3, 0.2, 0.4, 30),
    ("Unemployment Rate", "US", "USD", "high", 3.9, 3.8, 0.2, 30),
    ("Consumer Confidence", "US", "USD", "low", 102.0, 100.0, 5.0, 30),
    ("PPI y/y", "US", "USD", "medium", 2.2, 2.1, 0.3, 30),
]


def _phase_offset(event_name: str, cycle_days: int) -> int:
    digest = hashlib.sha256(event_name.encode()).hexdigest()
    return int(digest, 16) % cycle_days


def _occurrence_dates(event_name: str, cycle_days: int, start: datetime, end: datetime) -> list[datetime]:
    epoch = datetime(2020, 1, 1, 13, 30, tzinfo=timezone.utc)  # fixed anchor, arbitrary clock time
    phase = _phase_offset(event_name, cycle_days)
    first_cycle = ((start - epoch).days - phase) // cycle_days
    dates = []
    cycle = first_cycle
    while True:
        occurs_at = epoch + timedelta(days=phase + cycle * cycle_days)
        if occurs_at > end:
            break
        if occurs_at >= start:
            dates.append(occurs_at)
        cycle += 1
    return dates


class MockMacroCalendarProvider:
    name = "mock"

    def __init__(self) -> None:
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    def get_events(self, start: datetime, end: datetime) -> list[MacroEventItem]:
        now = datetime.now(timezone.utc)
        items: list[MacroEventItem] = []

        for event, country, currency, importance, base_forecast, base_previous, surprise_std, cycle_days in _TEMPLATES:
            for scheduled_at in _occurrence_dates(event, cycle_days, start, end):
                rng = random.Random(f"macro:{event}:{scheduled_at.date().isoformat()}")
                forecast = round(base_forecast + rng.uniform(-surprise_std * 0.5, surprise_std * 0.5), 2)
                previous = round(base_previous + rng.uniform(-surprise_std * 0.5, surprise_std * 0.5), 2)
                actual = None
                if scheduled_at <= now:
                    actual = round(forecast + rng.gauss(0, surprise_std), 2)
                items.append(
                    MacroEventItem(
                        event=event, country=country, currency=currency, scheduled_at=scheduled_at,
                        importance=importance, forecast=forecast, previous=previous, actual=actual,
                    )
                )

        items.sort(key=lambda i: i.scheduled_at)
        return items
