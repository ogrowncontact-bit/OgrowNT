from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.deps import get_session
from apps.api.schemas import CandleOut
from packages.shared.models import OHLCV, Asset

router = APIRouter(prefix="/api/market-data", tags=["market-data"])


def _get_asset_or_404(asset_id: int, db: Session) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@router.get("/{asset_id}", response_model=list[CandleOut])
def get_market_data(
    asset_id: int,
    timeframe: str = "1m",
    since: datetime | None = None,
    limit: int = 500,
    db: Session = Depends(get_session),
) -> list[OHLCV]:
    _get_asset_or_404(asset_id, db)
    query = db.query(OHLCV).filter(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe)
    if since is not None:
        query = query.filter(OHLCV.ts >= since)
    return query.order_by(OHLCV.ts.desc()).limit(limit).all()


@router.get("/{asset_id}/latest", response_model=CandleOut)
def get_latest_market_data(
    asset_id: int,
    timeframe: str = "1m",
    db: Session = Depends(get_session),
) -> OHLCV:
    _get_asset_or_404(asset_id, db)
    candle = (
        db.query(OHLCV)
        .filter(OHLCV.asset_id == asset_id, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.ts.desc())
        .first()
    )
    if candle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DATA_UNAVAILABLE")
    return candle
