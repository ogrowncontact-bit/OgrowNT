"""Failover Market Data Provider — "PROMPT 12" §52-53.

Wraps a primary and secondary MarketDataProvider behind the SAME protocol
(packages/data/connectors/market/base.py), so every existing caller
(apps/worker, agents, API) can use a FailoverMarketDataProvider exactly
like any other provider — no special-casing needed anywhere else.

Architecture-ready, not exercised against a real second provider: this
codebase has exactly one real provider implementation (MockMarketDataProvider
— see that module's own "THIS IS NOT A REAL DATA SOURCE" docstring), so
there is no genuine second live source to fail over to yet. Tests exercise
this module with two independent stub providers instead (the same honest-
scoping pattern used for Prompt 11's etf/future/bond/option asset-class
readiness — see docs/global-market-intelligence.md).

Failover itself never fabricates data: if BOTH providers fail to produce a
candle, the result is None (DATA_UNAVAILABLE), same as every other
provider's own contract — this module only ever chooses between two real
answers or reports honestly that it has neither.

DATA_CONFLICT (§53) is deliberately NOT checked on the hot path
(get_latest_candle/get_recent_candles only try the primary, then the
secondary, and return the first real answer) — cross_check_latest() is a
separate, explicit call for a periodic/on-demand comparison, the same
"not on every hot-path read" discipline packages/risk/correlation_guard.py
already applies to its own persisted-vs-per-check split.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from packages.data.connectors.market.base import Candle, MarketDataProvider

# How much a primary/secondary latest-close disagreement has to be before
# it's flagged as a genuine DATA_CONFLICT rather than ordinary cross-venue
# spread -- generous on purpose (this is meant to catch a source that is
# simply wrong or badly stale, not everyday quoting differences).
DEFAULT_CONFLICT_TOLERANCE_PCT = 0.5


@dataclass(frozen=True)
class CrossCheckResult:
    symbol: str
    timeframe: str
    primary_close: float | None
    secondary_close: float | None
    conflict: bool
    detail: str | None


class FailoverMarketDataProvider:
    name = "failover"

    def __init__(
        self, primary: MarketDataProvider, secondary: MarketDataProvider, *,
        conflict_tolerance_pct: float = DEFAULT_CONFLICT_TOLERANCE_PCT,
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._conflict_tolerance_pct = conflict_tolerance_pct
        # Observability, not behavior -- callers (a health check, a
        # dashboard) can read these to know whether failover has actually
        # happened, without this module needing its own DB table.
        self.active_provider_name: str | None = None
        self.last_failover_at: datetime | None = None

    def is_connected(self) -> bool:
        return self._primary.is_connected() or self._secondary.is_connected()

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        try:
            candle = self._primary.get_latest_candle(symbol, timeframe)
        except Exception:  # noqa: BLE001 -- a primary outage must not crash the caller, it must trigger failover
            candle = None
        if candle is not None:
            self.active_provider_name = self._primary.name
            return candle

        try:
            candle = self._secondary.get_latest_candle(symbol, timeframe)
        except Exception:  # noqa: BLE001
            candle = None
        if candle is not None:
            self.active_provider_name = self._secondary.name
            self.last_failover_at = datetime.now(timezone.utc)
            return candle

        self.active_provider_name = None  # neither source has data -- honest None, never a guess
        return None

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        try:
            candles = self._primary.get_recent_candles(symbol, timeframe, limit)
        except Exception:  # noqa: BLE001
            candles = []
        if candles:
            self.active_provider_name = self._primary.name
            return candles

        try:
            candles = self._secondary.get_recent_candles(symbol, timeframe, limit)
        except Exception:  # noqa: BLE001
            candles = []
        if candles:
            self.active_provider_name = self._secondary.name
            self.last_failover_at = datetime.now(timezone.utc)
        else:
            self.active_provider_name = None
        return candles

    def cross_check_latest(self, symbol: str, timeframe: str) -> CrossCheckResult:
        """Deliberately queries BOTH providers (unlike the failover reads
        above) -- the only way to actually know whether they agree."""
        try:
            primary_candle = self._primary.get_latest_candle(symbol, timeframe)
        except Exception:  # noqa: BLE001
            primary_candle = None
        try:
            secondary_candle = self._secondary.get_latest_candle(symbol, timeframe)
        except Exception:  # noqa: BLE001
            secondary_candle = None

        primary_close = primary_candle.close if primary_candle is not None else None
        secondary_close = secondary_candle.close if secondary_candle is not None else None

        if primary_close is None or secondary_close is None:
            return CrossCheckResult(
                symbol=symbol, timeframe=timeframe, primary_close=primary_close, secondary_close=secondary_close,
                conflict=False, detail="cannot cross-check -- at least one source has no data for this symbol",
            )

        diff_pct = abs(primary_close - secondary_close) / primary_close * 100 if primary_close else 0.0
        conflict = diff_pct > self._conflict_tolerance_pct
        detail = (
            f"DATA_CONFLICT: primary/secondary latest close differ by {diff_pct:.2f}% "
            f"(tolerance {self._conflict_tolerance_pct}%)"
            if conflict else None
        )
        return CrossCheckResult(
            symbol=symbol, timeframe=timeframe, primary_close=primary_close, secondary_close=secondary_close,
            conflict=conflict, detail=detail,
        )
