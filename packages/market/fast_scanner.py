"""Fast Market Scanner -- "PROMPT 11" §25-32.

Runs across the full paper-eligible universe on a short cadence, computing
a cheap composite `InitialOpportunityScore` per asset from indicators
already in packages/quant/indicators/core.py plus a lightweight news-
activity count. Nothing here runs a strategy, a pattern detector, or the
full Opportunity Scoring Engine (packages/quant/scoring) -- that stays the
job of the existing apps/worker/strategy_runner.py cycle (the spec's
"DeepMarketScanner"), which task "PROMPT 11" §92's apps/worker wiring will
restrict to running only against this scanner's Top-N output instead of
every asset every cycle.

"Price" and "spread" from the prompt's component list are deliberately
not separate scored dimensions here: a raw price level has no inherent
"better/worse" direction (it only matters relative to recent range, which
`range_position`/`breakout_proximity` already capture), and no order-book
feed exists anywhere in this codebase (see
packages/market/liquidity.py's module docstring) -- `asset.liquidity_score`,
already computed by MarketUniverseManager from the same proxy, stands in
for spread quality instead of a second, duplicate proxy.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.data.connectors.market.base import Candle
from packages.market.universe import is_paper_eligible
from packages.quant.indicators.core import avg_volume, realized_volatility, recent_high, recent_low, roc
from packages.shared.market_data import get_recent_candles
from packages.shared.models import Asset, NewsEvent, NewsImpact

logger = logging.getLogger("market.fast_scanner")

TIMEFRAME = "1m"
LOOKBACK_CANDLES = 30
NEWS_ACTIVITY_LOOKBACK_HOURS = 6.0
# "PROMPT 11" §26's configurable Top-N examples are 20/50/100; 20 fits this
# system's modest 22-asset seed universe without the fast/deep split being
# a no-op. Callers pass any N (see FastMarketScanner.scan).
DEFAULT_TOP_N = 20


@dataclass(frozen=True)
class InitialOpportunityScore:
    asset_id: int
    symbol: str
    score: float  # 0-100
    components: dict[str, float] = field(default_factory=dict)
    reason: str | None = None  # set when scored 0 for an honest "no data" reason, not a real 0


def _momentum_component(closes: list[float]) -> float:
    change = roc(closes, period=10)
    if change is None:
        return 50.0  # neutral -- not enough history yet, not "no momentum"
    # +/-5% over 10 bars maps to the 0-100 extremes; clamp beyond that.
    return max(0.0, min(100.0, 50.0 + change * 1000))


def _volatility_component(closes: list[float]) -> float:
    vol = realized_volatility(closes)
    if vol is None:
        return 50.0
    # A scanner should surface volatility EXPANSION as interesting (something
    # is moving), not penalize it the way a risk engine would -- reward it up
    # to a cap rather than treating high volatility as automatically bad.
    return max(0.0, min(100.0, vol * 2000))


def _volume_component(candles: list[Candle]) -> float:
    avg_vol = avg_volume(candles, period=min(20, len(candles))) if candles else None
    if not avg_vol or not candles:
        return 50.0
    current = candles[-1].volume
    return max(0.0, min(100.0, (current / avg_vol) * 50))


def _high_low(candles: list[Candle]) -> tuple[float | None, float | None]:
    lookback = min(20, len(candles))
    return recent_high(candles, lookback=lookback), recent_low(candles, lookback=lookback)


def _breakout_proximity_component(candles: list[Candle]) -> float:
    high, low = _high_low(candles)
    if high is None or low is None or high == low:
        return 50.0
    close = candles[-1].close
    distance_to_high = abs(high - close) / (high - low)
    distance_to_low = abs(close - low) / (high - low)
    proximity = 1.0 - min(distance_to_high, distance_to_low)
    return max(0.0, min(100.0, proximity * 100))


def _range_position_component(candles: list[Candle]) -> float:
    high, low = _high_low(candles)
    if high is None or low is None or high == low:
        return 50.0
    close = candles[-1].close
    return max(0.0, min(100.0, 100.0 * (close - low) / (high - low)))


def _news_activity_component(db: Session, asset_id: int, now: datetime) -> float:
    cutoff = now - timedelta(hours=NEWS_ACTIVITY_LOOKBACK_HOURS)
    count = (
        db.query(NewsImpact)
        .join(NewsEvent, NewsImpact.news_event_id == NewsEvent.id)
        .filter(NewsImpact.asset_id == asset_id, NewsEvent.published_at >= cutoff)
        .count()
    )
    # 4+ items in the lookback window is "very active news" -- saturate there
    # rather than letting an unusually newsy asset dominate the composite.
    return max(0.0, min(100.0, count * 25.0))


class FastMarketScanner:
    """One pass over the paper-eligible universe -- cheap indicators only,
    no strategy/pattern/regime evaluation.
    """

    def scan(
        self, db: Session, *, top_n: int = DEFAULT_TOP_N, now: datetime | None = None,
    ) -> list[InitialOpportunityScore]:
        now = now or datetime.now(timezone.utc)
        assets = [a for a in db.query(Asset).all() if is_paper_eligible(a)]
        scored = [self.score_asset(db, asset, now=now) for asset in assets]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_n]

    def score_asset(self, db: Session, asset: Asset, *, now: datetime | None = None) -> InitialOpportunityScore:
        now = now or datetime.now(timezone.utc)
        candles = get_recent_candles(db, asset.id, TIMEFRAME, LOOKBACK_CANDLES)
        if not candles:
            return InitialOpportunityScore(
                asset_id=asset.id, symbol=asset.symbol, score=0.0, reason="no recent candle data",
            )

        closes = [c.close for c in candles]
        components = {
            "momentum": _momentum_component(closes),
            "volatility": _volatility_component(closes),
            "volume": _volume_component(candles),
            "breakout_proximity": _breakout_proximity_component(candles),
            "range_position": _range_position_component(candles),
            "liquidity": asset.liquidity_score if asset.liquidity_score is not None else 50.0,
            "news_activity": _news_activity_component(db, asset.id, now),
        }
        score = round(sum(components.values()) / len(components), 2)
        return InitialOpportunityScore(asset_id=asset.id, symbol=asset.symbol, score=score, components=components)
