"""Opportunity Type Classification + Fingerprint + Expiration -- "PROMPT 11"
§14-15, §20-24.

A pure classifier: takes an evidence bundle already computed by the other
market engines (structure.py, volatility.py, multi_timeframe.py, and --
once built -- pairs.py) and maps it onto the prompt's closed 12-value
OPPORTUNITY TYPES vocabulary. Never touches the DB itself, mirroring
packages/quant/patterns/detector.py's pure-function shape -- the caller
(apps/worker wiring, "PROMPT 11" §92) gathers the evidence and persists
the result onto Signal.opportunity_type/fingerprint/expires_at.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from packages.market.multi_timeframe import AGREEMENT
from packages.market.structure import (
    BREAK_OF_STRUCTURE,
    CHANGE_OF_CHARACTER,
    NO_BREAK,
    STRUCTURE_DOWNTREND,
    STRUCTURE_UPTREND,
)
from packages.market.volatility import EVENT_COLLAPSE, EVENT_COMPRESSION, EVENT_EXPANSION, EVENT_SPIKE

# -- closed vocabulary -- matches ck_signals_opportunity_type exactly -----
BREAKOUT = "breakout"
BREAKDOWN = "breakdown"
TREND_CONTINUATION = "trend_continuation"
REVERSAL = "reversal"
MEAN_REVERSION = "mean_reversion"
MOMENTUM = "momentum"
VOLATILITY_EXPANSION = "volatility_expansion"
VOLATILITY_COMPRESSION = "volatility_compression"
RELATIVE_STRENGTH = "relative_strength"
RELATIVE_WEAKNESS = "relative_weakness"
EVENT_DRIVEN = "event_driven"
STATISTICAL_ARBITRAGE_CANDIDATE = "statistical_arbitrage_candidate"

OPPORTUNITY_TYPES = (
    BREAKOUT, BREAKDOWN, TREND_CONTINUATION, REVERSAL, MEAN_REVERSION, MOMENTUM, VOLATILITY_EXPANSION,
    VOLATILITY_COMPRESSION, RELATIVE_STRENGTH, RELATIVE_WEAKNESS, EVENT_DRIVEN, STATISTICAL_ARBITRAGE_CANDIDATE,
)

# "PROMPT 11" §22's mandatory expires_at. A flat default per type -- not
# claimed to be empirically calibrated, just a reasonable starting TTL an
# operator can retune later (e.g. via research findings feeding back into
# this table, same spirit as config/research_budget.yaml).
_DEFAULT_TTL = timedelta(hours=4)
_TTL_BY_TYPE: dict[str, timedelta] = {
    EVENT_DRIVEN: timedelta(hours=1),
    VOLATILITY_EXPANSION: timedelta(hours=2),
    MOMENTUM: timedelta(hours=2),
    BREAKOUT: timedelta(hours=4),
    BREAKDOWN: timedelta(hours=4),
    MEAN_REVERSION: timedelta(hours=4),
    REVERSAL: timedelta(hours=6),
    VOLATILITY_COMPRESSION: timedelta(hours=6),
    TREND_CONTINUATION: timedelta(hours=8),
    RELATIVE_STRENGTH: timedelta(hours=8),
    RELATIVE_WEAKNESS: timedelta(hours=8),
    STATISTICAL_ARBITRAGE_CANDIDATE: timedelta(hours=12),
}


@dataclass(frozen=True)
class OpportunityEvidence:
    """Everything `classify_opportunity_type` needs, pre-computed by the
    caller from the other market engines. Every field is optional --
    missing evidence just narrows which types can be inferred, never
    fabricated to force a classification.
    """

    structure: str | None = None  # packages.market.structure's STRUCTURE_*
    break_state: str | None = None  # packages.market.structure's BREAK_OF_STRUCTURE / CHANGE_OF_CHARACTER / NO_BREAK
    volatility_event_type: str | None = None  # packages.market.volatility's EVENT_*
    timeframe_agreement: str | None = None  # packages.market.multi_timeframe's AGREEMENT / CONFLICT / NEUTRAL / INSUFFICIENT_DATA
    range_position: float | None = None  # 0-100, from fast_scanner's range_position component
    relative_strength_percentile: float | None = None  # 0-100 vs asset-class peers
    news_shock: bool = False  # e.g. packages.market.anomaly's ANOMALY_NEWS_SHOCK fired for this asset
    pairs_signal: bool = False  # set once packages/market/pairs.py exists


@dataclass(frozen=True)
class OpportunityTypeResult:
    opportunity_type: str | None
    reason: str


def classify_opportunity_type(evidence: OpportunityEvidence) -> OpportunityTypeResult:
    """Priority order, most specific/concrete evidence first: a
    statistical-arbitrage or event-driven signal is checked before generic
    structural/momentum evidence, since those two are narrower, higher-
    conviction categories when present. Returns `opportunity_type=None`
    when nothing in the evidence bundle clears any bar -- "NO OPPORTUNITY"
    is itself a valid, honest outcome (§88), never forced.
    """
    if evidence.pairs_signal:
        return OpportunityTypeResult(STATISTICAL_ARBITRAGE_CANDIDATE, "cointegrated pair spread signal")
    if evidence.news_shock:
        return OpportunityTypeResult(EVENT_DRIVEN, "recent critical news/anomaly shock")

    if evidence.break_state == BREAK_OF_STRUCTURE and evidence.structure == STRUCTURE_UPTREND:
        return OpportunityTypeResult(BREAKOUT, "break of structure above the last swing high in an uptrend")
    if evidence.break_state == BREAK_OF_STRUCTURE and evidence.structure == STRUCTURE_DOWNTREND:
        return OpportunityTypeResult(BREAKDOWN, "break of structure below the last swing low in a downtrend")
    if evidence.break_state == CHANGE_OF_CHARACTER:
        return OpportunityTypeResult(REVERSAL, "change of character -- structure broke against the prevailing trend")

    if evidence.volatility_event_type in (EVENT_SPIKE, EVENT_EXPANSION):
        return OpportunityTypeResult(VOLATILITY_EXPANSION, f"volatility {evidence.volatility_event_type}")
    if evidence.volatility_event_type in (EVENT_COLLAPSE, EVENT_COMPRESSION):
        return OpportunityTypeResult(VOLATILITY_COMPRESSION, f"volatility {evidence.volatility_event_type}")

    if evidence.relative_strength_percentile is not None:
        if evidence.relative_strength_percentile >= 90.0:
            return OpportunityTypeResult(
                RELATIVE_STRENGTH, f"{evidence.relative_strength_percentile:.0f}th percentile vs asset-class peers",
            )
        if evidence.relative_strength_percentile <= 10.0:
            return OpportunityTypeResult(
                RELATIVE_WEAKNESS, f"{evidence.relative_strength_percentile:.0f}th percentile vs asset-class peers",
            )

    if (
        evidence.range_position is not None
        and (evidence.range_position <= 10.0 or evidence.range_position >= 90.0)
        and evidence.structure not in (STRUCTURE_UPTREND, STRUCTURE_DOWNTREND)
    ):
        return OpportunityTypeResult(
            MEAN_REVERSION, f"price at a range extreme ({evidence.range_position:.0f}) with no confirmed trend structure",
        )

    if evidence.structure in (STRUCTURE_UPTREND, STRUCTURE_DOWNTREND) and evidence.break_state == NO_BREAK:
        return OpportunityTypeResult(TREND_CONTINUATION, f"{evidence.structure} intact, no structural break yet")

    if evidence.timeframe_agreement == AGREEMENT:
        return OpportunityTypeResult(MOMENTUM, "multiple timeframes agree on direction without confirmed structure yet")

    return OpportunityTypeResult(None, "no evidence cleared any opportunity-type bar")


def _time_bucket(now: datetime, minutes: int) -> datetime:
    """Floor `now` to the start of its `minutes`-wide UTC epoch bucket --
    same epoch-arithmetic approach as multi_timeframe.py's resample_candles,
    correct for any bucket size (unlike a naive minute-of-hour modulo, which
    breaks once the bucket is wider than an hour).
    """
    epoch_minutes = int(now.timestamp() // 60)
    bucket_index = epoch_minutes // minutes
    return datetime.fromtimestamp(bucket_index * minutes * 60, tz=timezone.utc)


def compute_fingerprint(
    symbol: str, opportunity_type: str, direction: str, entry_price: float, *, price_bucket_pct: float = 0.5,
    time_bucket_minutes: int = 60, now: datetime | None = None,
) -> str:
    """A stable dedup key -- "PROMPT 11" §23. The SAME opportunity
    re-detected on consecutive scan cycles (same symbol/type/direction, a
    similar entry price, within the same coarse time window) collapses to
    the same fingerprint; a genuinely different setup does not.
    """
    now = now or datetime.now(timezone.utc)
    if entry_price > 0:
        # Geometric (log-space) bucketing: a fixed additive step in
        # log-price is a fixed PERCENTAGE step in real price, unlike
        # dividing by a step proportional to entry_price itself (which
        # degenerates to the same ratio, hence the same bucket, for every
        # price -- log-space is what makes "within price_bucket_pct%"
        # actually mean something here).
        price_bucket = round(math.log(entry_price) / math.log(1.0 + price_bucket_pct / 100.0))
    else:
        price_bucket = 0
    time_bucket = _time_bucket(now, time_bucket_minutes)

    raw = f"{symbol}|{opportunity_type}|{direction}|{price_bucket}|{time_bucket.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def compute_expiration(opportunity_type: str | None, *, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    ttl = _TTL_BY_TYPE.get(opportunity_type or "", _DEFAULT_TTL)
    return now + ttl
