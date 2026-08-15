"""Small shared OHLCV lookup used by both the Portfolio Engine (mark-to-market)
and the Execution Engine (simulated fills) — kept here instead of duplicated
in each, since both need exactly the same "latest known price" query.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

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
