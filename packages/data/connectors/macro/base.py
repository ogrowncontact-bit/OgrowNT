"""MacroCalendarProvider interface — Prompt 6 §3/§15.

Mirrors packages/data/connectors/{market,news}/base.py's shape exactly: a
small Protocol an adapter implements, so the rest of the system (ingestion,
Risk Engine, dashboard) is never coupled to one calendar source. Fetching a
calendar is deterministic — no LLM involved; forecast/previous/actual are
whatever the source reports, never invented.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

MACRO_IMPORTANCE_LEVELS = ("low", "medium", "high", "critical")


@dataclass(frozen=True)
class MacroEventItem:
    event: str
    country: str
    currency: str | None
    scheduled_at: datetime
    importance: str
    forecast: float | None
    previous: float | None
    # None until the event has genuinely occurred — Prompt 6 §16: "Não
    # assumir automaticamente direção do mercado" applies just as much to
    # "assuming a released number before it exists".
    actual: float | None


class MacroCalendarProvider(Protocol):
    name: str

    def is_connected(self) -> bool: ...

    def get_events(self, start: datetime, end: datetime) -> list[MacroEventItem]:
        """Every known event scheduled in [start, end], newest last. MUST
        return [] rather than invent an event the source doesn't have."""
        ...
