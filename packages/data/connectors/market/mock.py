"""Mock market data provider — Phase 1 default (MARKET_DATA_PROVIDER=mock).

Generates a deterministic pseudo-random walk per symbol so the scanner,
dashboard and tests have real numbers to move through the pipeline without
depending on network access or API keys during development.

THIS IS NOT A REAL DATA SOURCE. It must never be enabled outside local/dev
use. Before Phase 2 (real strategies acting on this data) or any live
capital, replace it with a real adapter implementing the same
MarketDataProvider protocol, e.g.:

    TODO(real-market-data): implement BinanceProvider / AlpacaProvider /
    a forex+equities feed behind packages/data/connectors/market/base.py,
    and switch MARKET_DATA_PROVIDER away from "mock" in production config.
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone

from packages.data.connectors.market.base import Candle

_BASE_PRICES = {
    "crypto": 30000.0,
    "forex": 1.10,
    "equity": 180.0,
    "index": 5000.0,
    "commodity": 2000.0,
}


class MockMarketDataProvider:
    name = "mock"

    def __init__(self) -> None:
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        base = self._base_price(symbol)
        rng = self._rng_for(symbol, timeframe)
        drift = rng.uniform(-0.004, 0.004)
        close = round(base * (1 + drift), 6)
        high = round(close * (1 + abs(rng.uniform(0, 0.002))), 6)
        low = round(close * (1 - abs(rng.uniform(0, 0.002))), 6)
        open_ = round(low + (high - low) * rng.random(), 6)
        volume = round(rng.uniform(1, 1000), 2)
        return Candle(
            ts=datetime.now(timezone.utc),
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            data_quality="high",
        )

    @staticmethod
    def _base_price(symbol: str) -> float:
        digest = hashlib.sha256(symbol.encode()).hexdigest()
        offset = (int(digest[:8], 16) % 2000) / 1000.0  # 0.0 - 2.0
        return _BASE_PRICES.get(MockMarketDataProvider._guess_class(symbol), 100.0) * (0.5 + offset / 2)

    @staticmethod
    def _guess_class(symbol: str) -> str:
        s = symbol.upper()
        if s.endswith("USDT") or s.endswith("BTC") or s.startswith("BTC") or s.startswith("ETH"):
            return "crypto"
        if len(s) == 6 and s.isalpha():
            return "forex"
        if s in {"SPX", "NDX", "DAX", "IBEX"}:
            return "index"
        if s in {"XAU", "XAG", "WTI", "BRENT"}:
            return "commodity"
        return "equity"

    @staticmethod
    def _rng_for(symbol: str, timeframe: str) -> random.Random:
        # Seeded by symbol + current minute so consecutive scans move the
        # price (random walk feel) while staying reproducible within a test.
        minute_bucket = int(datetime.now(timezone.utc).timestamp() // 60)
        seed = f"{symbol}:{timeframe}:{minute_bucket}"
        return random.Random(seed)
