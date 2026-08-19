"""Small shared OHLCV lookup used by both the Portfolio Engine (mark-to-market)
and the Execution Engine (simulated fills), and by the Market Data Agent
(apps/worker/scanner.py) and the /api/market/* read endpoints — kept here
instead of duplicated in each, since all of them need exactly the same
"recent known candles for this asset" query. apps/api never imports from
apps/worker (docs/blueprint/01-repo-structure.md), so this is the shared
home for it, same as get_latest_candle_row below.
"""
from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy.orm import Session

from packages.data.connectors.market.base import Candle, DataQuality
from packages.shared.models import OHLCV


def get_latest_candle_row(db: Session, asset_id: int, timeframe: str = "1m") -> OHLCV | None:
    return (
        db.query(OHLCV)
        .filter(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.ts.desc())
        .first()
    )


def get_latest_close(db: Session, asset_id: int, timeframe: str = "1m") -> float | None:
    row = get_latest_candle_row(db, asset_id, timeframe)
    return row.close if row else None


def get_close_at_or_after(db: Session, asset_id: int, ts: datetime, timeframe: str = "1m") -> float | None:
    """The first known close at or after `ts` — used by
    packages/quant/news/event_reaction.py to mark the price right as a news
    event/macro release lands. None (never an interpolated guess) when no
    candle that late exists yet."""
    row = (
        db.query(OHLCV)
        .filter(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe, OHLCV.ts >= ts)
        .order_by(OHLCV.ts.asc())
        .first()
    )
    return row.close if row else None


def get_recent_candles(db: Session, asset_id: int, timeframe: str, limit: int) -> list[Candle]:
    """Chronological ascending (oldest first), what indicators/event
    detection expect — the OHLCV rows themselves are stored/queried newest
    first since that's the more common read pattern elsewhere."""
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.ts.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        Candle(
            ts=r.ts, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume,
            data_quality=cast(DataQuality, r.data_quality),  # DB CHECK constraint guarantees a valid value
        )
        for r in rows
    ]
