"""SentimentWorker cycle — Prompt 6 §22/§36: detects SENTIMENT_SHIFT per
asset and raises an Alert when the shift crosses the threshold
(packages/quant/news/sentiment.py's compute_sentiment_shift) — a
descriptive signal only, never a trade ("Não transformar automaticamente
em trade").
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.quant.news.sentiment import compute_sentiment_shift
from packages.shared.models import Alert, Asset

logger = logging.getLogger("worker.sentiment_agent")

# Don't re-alert on the same still-ongoing shift every cycle.
REALERT_COOLDOWN_HOURS = 6.0


def _recently_alerted(db: Session, asset_id: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=REALERT_COOLDOWN_HOURS)
    recent = db.query(Alert).filter(Alert.category == "news", Alert.ts >= cutoff).all()
    return any(a.meta.get("marker") == "sentiment_shift" and a.meta.get("asset_id") == asset_id for a in recent)


def run_sentiment_shift_cycle(db: Session) -> dict:
    assets = db.query(Asset).filter(Asset.is_active.is_(True)).all()
    shifts_detected = 0

    for asset in assets:
        shift = compute_sentiment_shift(db, asset.id)
        if not shift.detected or shift.shift is None:
            continue
        if _recently_alerted(db, asset.id):
            continue

        direction = "more bullish" if shift.shift > 0 else "more bearish"
        db.add(
            Alert(
                severity="warning",
                category="news",
                message=(
                    f"Sentiment shift detected for {asset.symbol}: turning {direction} "
                    f"({shift.baseline_bullish_share:.0%} -> {shift.recent_bullish_share:.0%} bullish share)"
                ),
                meta={
                    "marker": "sentiment_shift", "asset_id": asset.id, "asset_symbol": asset.symbol,
                    "shift": shift.shift, "recent_bullish_share": shift.recent_bullish_share,
                    "baseline_bullish_share": shift.baseline_bullish_share,
                },
            )
        )
        shifts_detected += 1

    db.commit()
    summary = {"assets_checked": len(assets), "shifts_detected": shifts_detected}
    logger.info("Sentiment shift cycle complete: %s", summary)
    return summary
