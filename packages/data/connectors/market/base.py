"""MarketDataProvider interface.

Every market data source (mock or real) implements this protocol. Agents and
the API only ever depend on this interface, never on a concrete provider —
swapping "mock" for "binance"/"alpaca"/etc. later is a config change
(MARKET_DATA_PROVIDER env var), not a code change in the callers.

See docs/blueprint/04-agents-architecture.md#agent-02 and
docs/blueprint/08-risk-engine.md#data-quality-gate: a provider must report
DATA_UNAVAILABLE rather than invent a value it does not actually have.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

DataQuality = Literal["high", "degraded", "unavailable"]


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    data_quality: DataQuality = "high"


class MarketDataProvider(Protocol):
    name: str

    def is_connected(self) -> bool:
        """Cheap liveness check used by /api/system/health."""
        ...

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        """Return the most recent candle, or None if unavailable.

        Implementations MUST NOT fabricate a candle when the underlying
        source has nothing to report — return None (the caller records
        DATA_UNAVAILABLE) instead of guessing a price.
        """
        ...
