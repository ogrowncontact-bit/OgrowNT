"""Market Data Agent / Scanner — docs/blueprint/04-agents-architecture.md#agent-02.

Phase 1 responsibility only: poll the configured MarketDataProvider for every
active asset, run a minimal data-quality gate, and persist OHLCV. Pattern
detection, regime classification and signal generation arrive in later
phases (docs/blueprint/12-roadmap.md) and are not implemented here.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.data.connectors.market.base import Candle, MarketDataProvider
from packages.shared.models import OHLCV, Asset

logger = logging.getLogger("worker.scanner")

TIMEFRAME = "1m"


def _passes_data_quality(candle: Candle) -> bool:
    if candle.high < candle.low:
        return False
    if candle.close <= 0 or candle.open <= 0:
        return False
    if candle.volume < 0:
        return False
    return True


def run_scan_cycle(db: Session, provider: MarketDataProvider) -> dict:
    """One pass over all active assets. Returns a small summary for logging/tests."""
    assets = db.query(Asset).filter(Asset.is_active.is_(True)).all()
    scanned, stored, unavailable = 0, 0, 0

    for asset in assets:
        scanned += 1
        candle = provider.get_latest_candle(asset.symbol, TIMEFRAME)
        if candle is None:
            unavailable += 1
            logger.warning("DATA_UNAVAILABLE for %s (%s)", asset.symbol, TIMEFRAME)
            continue
        if not _passes_data_quality(candle):
            unavailable += 1
            logger.warning("Data quality check failed for %s: %s", asset.symbol, candle)
            continue

        db.merge(
            OHLCV(
                asset_id=asset.id,
                timeframe=TIMEFRAME,
                ts=candle.ts,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                data_quality=candle.data_quality,
            )
        )
        stored += 1

    db.commit()
    summary = {"scanned": scanned, "stored": stored, "unavailable": unavailable}
    logger.info("Scan cycle complete: %s", summary)
    return summary
