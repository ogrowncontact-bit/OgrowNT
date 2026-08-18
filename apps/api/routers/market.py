"""Prompt 2's Market Data Engine + Scanner read surface — distinct from the
existing /api/market-data/{asset_id} (raw OHLCV by internal id, Phase 1)
and /api/assets (asset CRUD): this router is the "Market Intelligence
Layer" view — symbol-keyed, metrics-enriched, and the home for
MarketEvent/data-quality reads that didn't exist before this module.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from apps.api.deps import get_current_admin, get_session
from apps.api.schemas import (
    CandleOut,
    DataQualityOut,
    DataSourceOut,
    MarketAssetOverviewOut,
    MarketEventOut,
    MarketOverviewOut,
)
from packages.data.connectors.market.base import MarketDataProvider
from packages.data.connectors.market.factory import get_market_data_provider
from packages.data.quality import compute_quality_score
from packages.quant.indicators.core import atr, realized_volatility, trend_strength
from packages.shared.market_data import get_recent_candles
from packages.shared.models import OHLCV, AdminUser, Asset, MarketEvent
from packages.shared.settings import get_settings

router = APIRouter(prefix="/api/market", tags=["market"])

TIMEFRAME = "1m"
# Matches apps/worker/scanner.py's _EVENT_WINDOW_CANDLES -- the same window
# the scanner uses to compute metrics, so the dashboard shows numbers
# consistent with what actually drove the last scan cycle's events.
_METRICS_WINDOW_CANDLES = 41


def _data_source(provider: MarketDataProvider) -> DataSourceOut:
    return DataSourceOut(provider=provider.name, is_live=provider.name != "mock")


def _trend_label(value: float | None) -> str | None:
    if value is None:
        return None
    if value > 0.1:
        return "up"
    if value < -0.1:
        return "down"
    return "flat"


def _asset_overview(db: Session, asset: Asset, provider: MarketDataProvider) -> MarketAssetOverviewOut:
    candles = get_recent_candles(db, asset.id, TIMEFRAME, _METRICS_WINDOW_CANDLES)
    unsafe_threshold = get_settings().market_data_quality_unsafe_threshold

    if not candles:
        quality = compute_quality_score(
            symbol=asset.symbol, latest_ts=None, timeframe=TIMEFRAME, candle_count=0,
            expected_count=_METRICS_WINDOW_CANDLES, last_data_quality=None,
            provider_connected=provider.is_connected(), unsafe_threshold=unsafe_threshold,
        )
        return MarketAssetOverviewOut(
            symbol=asset.symbol, asset_class=asset.asset_class, price=None, pct_change=None,
            volatility=None, volume=None, trend=None, data_quality_score=quality.quality_score,
            data_quality_status=quality.status, last_update=None,
        )

    latest = candles[-1]
    closes = [c.close for c in candles]
    pct_change = (latest.close - closes[-2]) / closes[-2] if len(closes) >= 2 and closes[-2] > 0 else None
    volatility = realized_volatility(closes, min(20, len(closes) - 1)) if len(closes) > 1 else None
    atr_value = atr(candles, min(14, len(candles) - 1)) if len(candles) > 1 else None
    trend = trend_strength(closes, atr_value) if atr_value is not None else None

    quality = compute_quality_score(
        symbol=asset.symbol, latest_ts=latest.ts, timeframe=TIMEFRAME, candle_count=len(candles),
        expected_count=_METRICS_WINDOW_CANDLES, last_data_quality=latest.data_quality,
        provider_connected=provider.is_connected(), unsafe_threshold=unsafe_threshold,
    )

    return MarketAssetOverviewOut(
        symbol=asset.symbol, asset_class=asset.asset_class, price=latest.close, pct_change=pct_change,
        volatility=volatility, volume=latest.volume, trend=_trend_label(trend),
        data_quality_score=quality.quality_score, data_quality_status=quality.status, last_update=latest.ts,
    )


def _get_active_asset_or_404(symbol: str, db: Session) -> Asset:
    asset = db.query(Asset).filter(Asset.symbol == symbol).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@router.get("/overview", response_model=MarketOverviewOut)
def market_overview(
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> MarketOverviewOut:
    provider = get_market_data_provider()
    assets = db.query(Asset).filter(Asset.is_active.is_(True)).order_by(Asset.symbol).all()
    return MarketOverviewOut(
        data_source=_data_source(provider),
        assets=[_asset_overview(db, asset, provider) for asset in assets],
    )


@router.get("/assets", response_model=list[MarketAssetOverviewOut])
def market_assets(
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[MarketAssetOverviewOut]:
    provider = get_market_data_provider()
    assets = db.query(Asset).filter(Asset.is_active.is_(True)).order_by(Asset.symbol).all()
    return [_asset_overview(db, asset, provider) for asset in assets]


@router.get("/events", response_model=list[MarketEventOut])
def market_events(
    symbol: str | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_session),
    _: AdminUser = Depends(get_current_admin),
) -> list[MarketEventOut]:
    query = db.query(MarketEvent).join(Asset, MarketEvent.asset_id == Asset.id)
    if symbol:
        query = query.filter(Asset.symbol == symbol)
    if event_type:
        query = query.filter(MarketEvent.event_type == event_type)
    if severity:
        query = query.filter(MarketEvent.severity == severity)
    rows = query.order_by(MarketEvent.ts.desc()).offset(offset).limit(limit).all()
    return [
        MarketEventOut(
            id=e.id, asset_symbol=e.asset.symbol, event_type=e.event_type, timeframe=e.timeframe,
            severity=e.severity, price=e.price, volume=e.volume, confidence=e.confidence, meta=e.meta, ts=e.ts,
        )
        for e in rows
    ]


@router.get("/data-quality", response_model=list[DataQualityOut])
def market_data_quality(
    db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> list[DataQualityOut]:
    provider = get_market_data_provider()
    unsafe_threshold = get_settings().market_data_quality_unsafe_threshold
    assets = db.query(Asset).filter(Asset.is_active.is_(True)).order_by(Asset.symbol).all()
    reports = []
    for asset in assets:
        candles = get_recent_candles(db, asset.id, TIMEFRAME, _METRICS_WINDOW_CANDLES)
        latest = candles[-1] if candles else None
        quality = compute_quality_score(
            symbol=asset.symbol, latest_ts=latest.ts if latest else None, timeframe=TIMEFRAME,
            candle_count=len(candles), expected_count=_METRICS_WINDOW_CANDLES,
            last_data_quality=latest.data_quality if latest else None,
            provider_connected=provider.is_connected(), unsafe_threshold=unsafe_threshold,
        )
        reports.append(
            DataQualityOut(
                symbol=quality.symbol, quality_score=quality.quality_score, status=quality.status,
                components=quality.components, detail=quality.detail,
            )
        )
    return reports


@router.get("/{symbol}", response_model=MarketAssetOverviewOut)
def market_asset_detail(
    symbol: str, db: Session = Depends(get_session), _: AdminUser = Depends(get_current_admin)
) -> MarketAssetOverviewOut:
    asset = _get_active_asset_or_404(symbol, db)
    provider = get_market_data_provider()
    return _asset_overview(db, asset, provider)


@router.get("/{symbol}/ohlcv", response_model=list[CandleOut])
def market_asset_ohlcv(
    symbol: str,
    timeframe: str = TIMEFRAME,
    since: datetime | None = None,
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_session),
    _: AdminUser = Depends(get_current_admin),
) -> list[OHLCV]:
    asset = _get_active_asset_or_404(symbol, db)
    query = db.query(OHLCV).filter(OHLCV.asset_id == asset.id, OHLCV.timeframe == timeframe)
    if since is not None:
        query = query.filter(OHLCV.ts >= since)
    return query.order_by(OHLCV.ts.desc()).limit(limit).all()
