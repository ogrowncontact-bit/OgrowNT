"""Market Data Agent / Scanner — docs/blueprint/04-agents-architecture.md#agent-02.

Poll the configured MarketDataProvider for every active asset, validate what
comes back (packages/data/validation.py), store it, then run the lightweight
real-time event detectors (packages/quant/market/events.py) that turn a
candle into PRICE_MOVEMENT/VOLUME_SPIKE/... candidates for a dashboard
ticker and, later, the Pattern/Strategy Engines. This module owns raw market
surveillance only -- regime classification, pattern detection and signal
generation happen in apps/worker/strategy_runner.py's separate cadence.

A single asset's provider error or a bug in event detection must not stop
the rest of the batch (Prompt 2's completion checklist: "falha de provider
não derruba o sistema") -- everything below is scoped per-asset with its
own try/except.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from apps.worker.market_alerts import MarketAlertTracker
from packages.data.connectors.market.base import MarketDataProvider
from packages.data.validation import validate_candle
from packages.quant.market.events import detect_events
from packages.shared.market_data import get_latest_candle_row, get_recent_candles
from packages.shared.models import OHLCV, Asset, MarketEvent

logger = logging.getLogger("worker.scanner")

TIMEFRAME = "1m"

# detect_events needs 2x its lookback window (packages/quant/market/events.py's
# VOLATILITY_SPIKE baseline) plus the freshly stored candle.
_EVENT_WINDOW_CANDLES = 41

# High-severity events are worth an operator alert; LOW/MEDIUM are dashboard-only.
_ALERTABLE_SEVERITIES = {"HIGH": "warning", "CRITICAL": "critical"}


def run_scan_cycle(db: Session, provider: MarketDataProvider, tracker: MarketAlertTracker | None = None) -> dict:
    """One pass over all active assets. Returns a small summary for logging/tests."""
    tracker = tracker or MarketAlertTracker()
    assets = db.query(Asset).filter(Asset.is_active.is_(True)).all()
    scanned, stored, unavailable, invalid, events_created = 0, 0, 0, 0, 0

    if not provider.is_connected():
        tracker.maybe_alert(
            db, key=f"feed_disconnected:{provider.name}", severity="critical",
            message=f"Market data provider '{provider.name}' is disconnected — no candles can be fetched.",
            meta={"provider": provider.name},
        )
        summary = {"scanned": 0, "stored": 0, "unavailable": len(assets), "invalid": 0, "events": 0}
        logger.error("Provider %s disconnected — skipping scan cycle", provider.name)
        return summary
    tracker.clear(f"feed_disconnected:{provider.name}")

    for asset in assets:
        scanned += 1
        try:
            candle = provider.get_latest_candle(asset.symbol, TIMEFRAME)
        except Exception:  # noqa: BLE001 - one bad symbol must not stop the batch
            logger.exception("Provider error fetching %s (%s)", asset.symbol, TIMEFRAME)
            unavailable += 1
            tracker.maybe_alert(
                db, key=f"provider_error:{asset.symbol}", severity="warning",
                message=f"Market data provider error fetching {asset.symbol}",
                meta={"symbol": asset.symbol, "provider": provider.name},
            )
            continue

        if candle is None:
            unavailable += 1
            logger.warning("DATA_UNAVAILABLE for %s (%s)", asset.symbol, TIMEFRAME)
            continue

        try:
            previous = get_latest_candle_row(db, asset.id, TIMEFRAME)
            result = validate_candle(candle, timeframe=TIMEFRAME, previous_close=previous.close if previous else None)
            if not result.valid:
                invalid += 1
                unavailable += 1
                logger.warning("INVALID_MARKET_DATA for %s: %s", asset.symbol, "; ".join(result.reasons))
                db.add(
                    MarketEvent(
                        asset_id=asset.id, event_type="INVALID_MARKET_DATA", timeframe=TIMEFRAME,
                        severity="MEDIUM", price=candle.close, volume=candle.volume, confidence=1.0,
                        meta={"reasons": result.reasons},
                    )
                )
                db.commit()
                tracker.maybe_alert(
                    db, key=f"invalid_data:{asset.symbol}", severity="warning",
                    message=f"Invalid market data for {asset.symbol}: {'; '.join(result.reasons)}",
                    meta={"symbol": asset.symbol, "reasons": result.reasons},
                )
                continue

            db.merge(
                OHLCV(
                    asset_id=asset.id, timeframe=TIMEFRAME, ts=candle.ts,
                    open=candle.open, high=candle.high, low=candle.low, close=candle.close,
                    volume=candle.volume, data_quality=candle.data_quality,
                )
            )
            db.commit()
            stored += 1

            recent = get_recent_candles(db, asset.id, TIMEFRAME, _EVENT_WINDOW_CANDLES)
            for candidate in detect_events(recent):
                db.add(
                    MarketEvent(
                        asset_id=asset.id, event_type=candidate.event_type, timeframe=TIMEFRAME,
                        severity=candidate.severity, price=candidate.price, volume=candidate.volume,
                        confidence=candidate.confidence, meta=candidate.metadata,
                    )
                )
                events_created += 1
                alert_severity = _ALERTABLE_SEVERITIES.get(candidate.severity)
                if alert_severity:
                    tracker.maybe_alert(
                        db, key=f"event:{asset.symbol}:{candidate.event_type}", severity=alert_severity,
                        message=f"{asset.symbol}: {candidate.event_type} ({candidate.severity})",
                        meta={"symbol": asset.symbol, "event_type": candidate.event_type, **candidate.metadata},
                    )
            db.commit()
        except Exception:  # noqa: BLE001 - validation/event-detection bug must not stop the batch
            logger.exception("Scan failed for %s after fetching a candle", asset.symbol)
            db.rollback()  # clear any failed-commit state before the next asset's queries
            unavailable += 1

    summary = {"scanned": scanned, "stored": stored, "unavailable": unavailable, "invalid": invalid, "events": events_created}
    logger.info("Scan cycle complete: %s", summary)
    return summary
