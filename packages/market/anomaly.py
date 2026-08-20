"""Anomaly Scanner -- "PROMPT 11" §45-49.

"An anomaly means INVESTIGATE, not TRADE" -- every AnomalyScore below is
evidence to look at, never a signal to act on. Nothing in this module (or
anywhere reading its output) creates an order from an anomaly alone -- the
scanner NEVER executes a trade (§95).

Five of the six closed `anomaly_type` values (packages/shared/models.py's
ck_anomalies_anomaly_type) are backed by real detection, reusing
primitives that already exist elsewhere in this codebase rather than
re-deriving new math for each:

    price_move             packages/quant/patterns/detector.py::detect_anomaly
                            (single-bar return z-score outlier), called fresh
    volume_spike            the existing VOLUME_SPIKE MarketEvent already
                            produced every scan cycle by
                            packages/quant/market/events.py via
                            apps/worker/scanner.py
    volatility_spike         packages/market/volatility.py's VolatilityEngine
                            SPIKE/COLLAPSE regime transition
    correlation_breakdown  packages/quant/patterns/detector.py::detect_cross_asset
                            against packages/risk/correlation_guard.py's
                            persisted correlation matrix -- wired here for
                            the first time anywhere in this codebase
                            (detect_cross_asset previously existed but was
                            never called by anything)
    news_shock              a NewsEvent with importance="critical" linked to
                            this asset via NewsImpact, in the recent
                            lookback window. A currency-level MacroEvent
                            path (matching on the new Asset.currency
                            column) would be a reasonable future extension
                            but isn't implemented here -- scoped out rather
                            than half-built.

`spread_expansion` is NOT emitted: no order-book feed exists anywhere in
this codebase (see packages/market/liquidity.py's module docstring) --
there is nothing principled to threshold without one.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from packages.data.connectors.market.base import Candle
from packages.market.volatility import EVENT_COLLAPSE, EVENT_SPIKE, VolatilityEngine
from packages.quant.indicators.core import compute_indicators
from packages.quant.market.events import EVENT_VOLUME_SPIKE
from packages.quant.patterns.detector import detect_anomaly, detect_cross_asset
from packages.risk.config import load_risk_limits
from packages.shared.market_data import get_recent_candles
from packages.shared.models import Anomaly, Asset, CorrelationMatrixEntry, MarketEvent, NewsEvent, NewsImpact

logger = logging.getLogger("market.anomaly")

TIMEFRAME = "1m"

ANOMALY_PRICE_MOVE = "price_move"
ANOMALY_VOLUME_SPIKE = "volume_spike"
ANOMALY_VOLATILITY_SPIKE = "volatility_spike"
ANOMALY_CORRELATION_BREAKDOWN = "correlation_breakdown"
ANOMALY_NEWS_SHOCK = "news_shock"
# ANOMALY_SPREAD_EXPANSION intentionally never emitted -- see module docstring.

_RECENT_EVENT_LOOKBACK = timedelta(minutes=15)
_RECENT_NEWS_LOOKBACK = timedelta(hours=6)
# A coarse, deliberately-uncalibrated qualitative score -- "critical
# importance" is itself a categorical judgment (packages/quant/news), not a
# continuous statistic like the z-scores the other detectors produce, so a
# fabricated-precision formula on top of it would be dishonest.
_NEWS_SHOCK_SCORE = 75.0


def _latest_return(candles: list[Candle]) -> float | None:
    if len(candles) < 2:
        return None
    prev, latest = candles[-2], candles[-1]
    if prev.close == 0:
        return None
    return (latest.close - prev.close) / prev.close


@dataclass(frozen=True)
class AnomalyFinding:
    asset_id: int
    symbol: str
    anomaly_type: str
    score: float
    evidence: dict


class AnomalyScanner:
    """Runs every detector above against one asset and persists an
    `Anomaly` row for each genuine finding. Every persisted row starts
    `reviewed=False` -- clearing it is a human (or a later research cycle)
    action, never automatic.
    """

    def scan_asset(
        self, db: Session, asset_id: int, symbol: str, *, timeframe: str = TIMEFRAME, now: datetime | None = None,
    ) -> list[AnomalyFinding]:
        now = now or datetime.now(timezone.utc)
        findings = [
            f for f in (
                self._scan_price_move(db, asset_id, symbol, timeframe),
                self._scan_volume_spike(db, asset_id, symbol, now),
                self._scan_volatility(db, asset_id, symbol, timeframe, now),
                self._scan_correlation_breakdown(db, asset_id, symbol, timeframe),
                self._scan_news_shock(db, asset_id, symbol, now),
            ) if f is not None
        ]

        for finding in findings:
            db.add(
                Anomaly(
                    asset_id=finding.asset_id, anomaly_type=finding.anomaly_type, score=finding.score,
                    evidence=finding.evidence,
                )
            )
        if findings:
            db.commit()
        return findings

    def _scan_price_move(self, db: Session, asset_id: int, symbol: str, timeframe: str) -> AnomalyFinding | None:
        candles = get_recent_candles(db, asset_id, timeframe, 30)
        if len(candles) < 21:
            return None
        detection = detect_anomaly(candles, compute_indicators(candles))
        if detection is None:
            return None
        return AnomalyFinding(
            asset_id=asset_id, symbol=symbol, anomaly_type=ANOMALY_PRICE_MOVE,
            score=round(detection.strength * 100, 2), evidence={"direction": detection.direction, **detection.metadata},
        )

    def _scan_volume_spike(self, db: Session, asset_id: int, symbol: str, now: datetime) -> AnomalyFinding | None:
        cutoff = now - _RECENT_EVENT_LOOKBACK
        event = (
            db.query(MarketEvent)
            .filter(
                MarketEvent.asset_id == asset_id, MarketEvent.event_type == EVENT_VOLUME_SPIKE,
                MarketEvent.ts >= cutoff,
            )
            .order_by(MarketEvent.ts.desc())
            .first()
        )
        if event is None:
            return None
        return AnomalyFinding(
            asset_id=asset_id, symbol=symbol, anomaly_type=ANOMALY_VOLUME_SPIKE,
            score=round(event.confidence * 100, 2), evidence={"severity": event.severity, "volume": event.volume, **event.meta},
        )

    def _scan_volatility(self, db: Session, asset_id: int, symbol: str, timeframe: str, now: datetime) -> AnomalyFinding | None:
        reading = VolatilityEngine().analyze(db, asset_id, symbol, timeframe=timeframe, now=now)
        if reading.event_type not in (EVENT_SPIKE, EVENT_COLLAPSE):
            return None
        return AnomalyFinding(
            asset_id=asset_id, symbol=symbol, anomaly_type=ANOMALY_VOLATILITY_SPIKE,
            score=round(reading.percentile or 0.0, 2),
            evidence={"event_type": reading.event_type, "regime": reading.regime, "realized_vol": reading.realized_vol},
        )

    def _scan_correlation_breakdown(self, db: Session, asset_id: int, symbol: str, timeframe: str) -> AnomalyFinding | None:
        limits = load_risk_limits()
        entry = (
            db.query(CorrelationMatrixEntry)
            .filter(or_(CorrelationMatrixEntry.asset_id_a == asset_id, CorrelationMatrixEntry.asset_id_b == asset_id))
            .order_by(CorrelationMatrixEntry.ts.desc())
            .first()
        )
        if entry is None or abs(entry.correlation) < limits.portfolio.correlation_threshold:
            return None
        peer_id = entry.asset_id_b if entry.asset_id_a == asset_id else entry.asset_id_a

        own_return = _latest_return(get_recent_candles(db, asset_id, timeframe, 2))
        peer_return = _latest_return(get_recent_candles(db, peer_id, timeframe, 2))
        peer_asset = db.get(Asset, peer_id)
        detection = detect_cross_asset(own_return, peer_return, peer_asset.symbol if peer_asset else str(peer_id))
        if detection is None:
            return None
        return AnomalyFinding(
            asset_id=asset_id, symbol=symbol, anomaly_type=ANOMALY_CORRELATION_BREAKDOWN,
            score=round(detection.strength * 100, 2), evidence={"correlation": entry.correlation, **detection.metadata},
        )

    def _scan_news_shock(self, db: Session, asset_id: int, symbol: str, now: datetime) -> AnomalyFinding | None:
        cutoff = now - _RECENT_NEWS_LOOKBACK
        event = (
            db.query(NewsEvent)
            .join(NewsImpact, NewsImpact.news_event_id == NewsEvent.id)
            .filter(
                NewsImpact.asset_id == asset_id, NewsEvent.importance == "critical",
                NewsEvent.published_at >= cutoff,
            )
            .order_by(NewsEvent.published_at.desc())
            .first()
        )
        if event is None:
            return None
        return AnomalyFinding(
            asset_id=asset_id, symbol=symbol, anomaly_type=ANOMALY_NEWS_SHOCK, score=_NEWS_SHOCK_SCORE,
            evidence={"headline": event.headline, "source": event.source},
        )
