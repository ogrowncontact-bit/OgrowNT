"""Backfill enough OHLCV history for indicators/strategies to run.

Real-time scanning (apps/worker/scanner.py) only ever adds one candle per
cycle, so a freshly seeded asset would need MIN_CANDLES_REQUIRED real
minutes before the Strategy Engine could do anything. This module fetches
historical bars from the provider once per asset instead of waiting.
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.data.connectors.market.base import MarketDataProvider
from packages.quant.indicators.core import MIN_CANDLES_REQUIRED
from packages.shared.models import OHLCV, Asset

TIMEFRAME = "1m"

logger = logging.getLogger("worker.history")

# A little above the strictly-required minimum so the very first strategy
# cycle after backfill already has margin (rolling windows, warm-up, etc).
BACKFILL_BARS = MIN_CANDLES_REQUIRED + 30


def ensure_min_history(db: Session, provider: MarketDataProvider, asset: Asset, timeframe: str) -> int:
    """Backfill this asset/timeframe if it has fewer than MIN_CANDLES_REQUIRED
    rows. Returns how many candles were inserted (0 if already sufficient)."""
    count = db.scalar(
        select(func.count()).select_from(OHLCV).where(OHLCV.asset_id == asset.id, OHLCV.timeframe == timeframe)
    ) or 0
    if count >= MIN_CANDLES_REQUIRED:
        return 0

    candles = provider.get_recent_candles(asset.symbol, timeframe, BACKFILL_BARS)
    if not candles:
        logger.warning("DATA_UNAVAILABLE backfilling %s (%s)", asset.symbol, timeframe)
        return 0

    for candle in candles:
        db.merge(
            OHLCV(
                asset_id=asset.id,
                timeframe=timeframe,
                ts=candle.ts,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                data_quality=candle.data_quality,
            )
        )
    db.commit()
    logger.info("Backfilled %d candles for %s (%s)", len(candles), asset.symbol, timeframe)
    return len(candles)


def backfill_active_assets(db: Session, provider: MarketDataProvider, timeframe: str = TIMEFRAME) -> int:
    """Cheap to call every cycle: ensure_min_history is a no-op once an
    asset already has enough history, so this only does real work for
    newly-added assets."""
    total = 0
    for asset in db.query(Asset).filter(Asset.is_active.is_(True)).all():
        total += ensure_min_history(db, provider, asset, timeframe)
    return total
