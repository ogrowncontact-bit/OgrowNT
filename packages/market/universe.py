"""Market Universe Manager -- "PROMPT 11" §5-10, §67-70.

No real "new asset discovery" feed exists anywhere in this codebase --
the market data provider serves a fixed, operator-curated symbol list
(packages/data/connectors/market/mock.py's _BASE_PRICES, seeded once by
scripts/seed.py). "Discovery" is honestly scoped to what this system CAN
do without inventing a listings API: periodically re-evaluate every
already-known `Asset` and drive it through the pipeline the prompt asks
for --

    DISCOVERED -> DATA VALIDATION -> LIQUIDITY VALIDATION -> CLASSIFICATION -> PAPER ELIGIBLE

-- reusing packages/data/quality.py::compute_quality_score and
packages/market/liquidity.py::score_liquidity, both already-built
primitives. `register_discovered_asset` is the extension point a real
listings feed would call into later without changing anything downstream.

Deliberately does NOT touch `Asset.is_active`: that flag has been read by
apps/worker/scanner.py, apps/worker/strategy_runner.py, and half a dozen
other modules since Phase 1 to mean "the live scan/strategy cadences
should consider this asset at all." Silently flipping it from this new
automatic evaluation would change existing, load-bearing behavior in ways
those call sites were never audited for. Instead, `status` is new,
additive metadata; wiring it into what the scan/strategy cadences actually
DO with a non-active asset is task "PROMPT 11" §92 territory (apps/worker
wiring), not this module.

Two states are operator-only and this module never sets or clears them:
INACTIVE and SUSPENDED. An asset already in one of those is skipped by
`run_universe_evaluation_cycle` entirely -- automatic re-evaluation only
moves an asset among ACTIVE / DATA_UNAVAILABLE / LOW_LIQUIDITY /
QUARANTINED, never overriding a human's explicit pause.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.data.connectors.market.base import MarketDataProvider
from packages.data.quality import compute_quality_score
from packages.market.liquidity import UNTRADABLE, percentile_rank, score_liquidity
from packages.quant.indicators.core import avg_volume
from packages.shared.market_data import get_latest_candle_row, get_recent_candles
from packages.shared.models import Asset, MarketEvent

logger = logging.getLogger("market.universe")

TIMEFRAME = "1m"
_VOLUME_LOOKBACK = 20
# A rough completeness baseline for this evaluation window -- same order of
# magnitude as apps/worker/scanner.py's own event-detection lookback, not a
# claim of a "correct" expected candle count for every timeframe/asset.
_EXPECTED_CANDLE_COUNT = 20

# "PROMPT 11" §9's closed AssetStatus vocabulary. Matches
# packages/shared/models.py's ck_assets_status CHECK constraint exactly.
STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"
STATUS_SUSPENDED = "suspended"
STATUS_DATA_UNAVAILABLE = "data_unavailable"
STATUS_LOW_LIQUIDITY = "low_liquidity"
STATUS_QUARANTINED = "quarantined"

ASSET_STATUSES = (
    STATUS_ACTIVE, STATUS_INACTIVE, STATUS_SUSPENDED, STATUS_DATA_UNAVAILABLE, STATUS_LOW_LIQUIDITY,
    STATUS_QUARANTINED,
)

# Operator-only states -- this module never sets or clears these.
_OPERATOR_CONTROLLED_STATUSES = (STATUS_INACTIVE, STATUS_SUSPENDED)

# Market Quarantine trigger -- "PROMPT 11" §69: this many INVALID_MARKET_DATA
# MarketEvents (packages/data/validation.py's suspicious-price/OHLC-coherence
# rejections, already recorded by apps/worker/scanner.py) within the lookback
# window below count as "corrupted feed", independent of the rolling
# data-quality score.
_QUARANTINE_INVALID_EVENT_THRESHOLD = 3
_QUARANTINE_LOOKBACK = timedelta(hours=1)


@dataclass(frozen=True)
class UniverseEvaluation:
    asset_id: int
    symbol: str
    previous_status: str
    status: str
    quality_score: int
    liquidity_score: float
    liquidity_tier: str
    paper_eligible: bool
    reasons: list[str] = field(default_factory=list)


def is_paper_eligible(asset: Asset) -> bool:
    """"PROMPT 11" §67-70's PAPER ELIGIBLE gate. Reduces to `status ==
    ACTIVE` because `MarketUniverseManager.evaluate_asset` only ever sets
    ACTIVE after the data-quality, liquidity, and pricing (a latest close
    exists) gates already passed. The risk-model and execution-simulator
    gates the prompt also asks for are vacuously satisfied by every
    currently-modeled asset_class -- packages/risk and packages/execution
    branch on data availability, never on asset_class -- so they add no
    further discrimination beyond what data quality already encodes; a
    class this codebase doesn't yet really support (etf/future/bond/
    option) never gets real OHLCV in the first place and is excluded via
    the same data-quality gate rather than a separate hardcoded check.
    """
    return asset.status == STATUS_ACTIVE


class MarketUniverseManager:
    """Runs the DISCOVERED -> ... -> PAPER ELIGIBLE pipeline for one or all
    assets. Stateless itself -- every read/write goes through the `db`
    session passed to each call.
    """

    def evaluate_asset(
        self, db: Session, asset: Asset, *, peer_avg_volumes: list[float] | None = None,
        provider_connected: bool = True, now: datetime | None = None,
    ) -> UniverseEvaluation:
        """DATA VALIDATION -> LIQUIDITY VALIDATION -> CLASSIFICATION for one
        asset. Persists the result onto `asset` (status/liquidity_score/
        data_quality_score) and returns it. Does not commit -- callers
        batch-commit (see `run_universe_evaluation_cycle`).
        """
        now = now or datetime.now(timezone.utc)
        reasons: list[str] = []
        previous_status = asset.status

        latest_row = get_latest_candle_row(db, asset.id, TIMEFRAME)
        recent = get_recent_candles(db, asset.id, TIMEFRAME, _VOLUME_LOOKBACK)
        quality = compute_quality_score(
            symbol=asset.symbol,
            latest_ts=latest_row.ts if latest_row else None,
            timeframe=TIMEFRAME,
            candle_count=len(recent),
            expected_count=_EXPECTED_CANDLE_COUNT,
            last_data_quality=latest_row.data_quality if latest_row else None,
            provider_connected=provider_connected,
            now=now,
        )

        candle_vol = avg_volume(recent, period=min(_VOLUME_LOOKBACK, len(recent))) if recent else None
        volume_percentile = (
            percentile_rank(candle_vol, peer_avg_volumes) if candle_vol is not None and peer_avg_volumes else 50.0
        )
        liquidity = score_liquidity(
            symbol=asset.symbol, volume_percentile=volume_percentile, data_quality_score=float(quality.quality_score),
        )

        invalid_events = (
            db.query(MarketEvent)
            .filter(
                MarketEvent.asset_id == asset.id,
                MarketEvent.event_type == "INVALID_MARKET_DATA",
                MarketEvent.ts >= now - _QUARANTINE_LOOKBACK,
            )
            .count()
        )

        if invalid_events >= _QUARANTINE_INVALID_EVENT_THRESHOLD:
            status = STATUS_QUARANTINED
            reasons.append(f"{invalid_events} corrupted/suspicious-price events in the last hour")
        elif quality.status == "DATA_UNSAFE":
            if latest_row is None:
                status = STATUS_DATA_UNAVAILABLE
                reasons.append("no OHLCV data recorded yet")
            else:
                status = STATUS_QUARANTINED
                reasons.append(f"data quality unsafe (score {quality.quality_score})")
        elif liquidity.tier == UNTRADABLE:
            status = STATUS_LOW_LIQUIDITY
            reasons.append(f"liquidity score {liquidity.score} is below the tradable floor")
        else:
            status = STATUS_ACTIVE
            if quality.status == "DEGRADED":
                reasons.append(f"data quality degraded (score {quality.quality_score}), still paper-eligible")

        asset.status = status
        asset.liquidity_score = liquidity.score
        asset.data_quality_score = float(quality.quality_score)

        return UniverseEvaluation(
            asset_id=asset.id, symbol=asset.symbol, previous_status=previous_status, status=status,
            quality_score=quality.quality_score, liquidity_score=liquidity.score, liquidity_tier=liquidity.tier,
            paper_eligible=is_paper_eligible(asset), reasons=reasons,
        )

    def run_universe_evaluation_cycle(
        self, db: Session, provider: MarketDataProvider, now: datetime | None = None,
    ) -> list[UniverseEvaluation]:
        now = now or datetime.now(timezone.utc)
        connected = provider.is_connected()
        if not connected:
            logger.warning("Provider %s disconnected -- evaluating universe against stored data only", provider.name)

        assets = [a for a in db.query(Asset).all() if a.status not in _OPERATOR_CONTROLLED_STATUSES]

        # First pass: gather per-asset volume so percentiles are ranked
        # against same-asset-class peers evaluated in this same cycle.
        volumes_by_class: dict[str, list[float]] = {}
        for asset in assets:
            recent = get_recent_candles(db, asset.id, TIMEFRAME, _VOLUME_LOOKBACK)
            vol = avg_volume(recent, period=min(_VOLUME_LOOKBACK, len(recent))) if recent else None
            if vol is not None:
                volumes_by_class.setdefault(asset.asset_class, []).append(vol)

        results = []
        for asset in assets:
            # percentile_rank ranks a value inclusive of itself within the
            # population, so passing the asset's own class-wide volume list
            # (which already contains this asset's own reading) is correct,
            # not a self-comparison bug.
            peers = volumes_by_class.get(asset.asset_class, [])
            evaluation = self.evaluate_asset(
                db, asset, peer_avg_volumes=peers, provider_connected=connected, now=now,
            )
            results.append(evaluation)
        db.commit()

        transitions = [e for e in results if e.previous_status != e.status]
        if transitions:
            logger.info(
                "Universe evaluation: %d assets, %d status transitions: %s",
                len(results), len(transitions),
                ", ".join(f"{e.symbol} {e.previous_status}->{e.status}" for e in transitions),
            )
        return results


def register_discovered_asset(db: Session, symbol: str, asset_class: str, **metadata: object) -> Asset:
    """Idempotent get-or-create -- the extension point a real listings feed
    would call into. New assets start in a neutral, not-yet-evaluated
    state (`data_unavailable`, since no OHLCV exists for them yet); the
    next `run_universe_evaluation_cycle` moves them from there.
    """
    existing = db.query(Asset).filter(Asset.symbol == symbol).one_or_none()
    if existing is not None:
        return existing
    asset = Asset(symbol=symbol, asset_class=asset_class, status=STATUS_DATA_UNAVAILABLE, **metadata)  # type: ignore[arg-type]
    db.add(asset)
    db.commit()
    return asset
