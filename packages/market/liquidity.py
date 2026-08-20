"""Liquidity Engine -- "PROMPT 11" §9-10, §71-73.

No real order-book feed exists anywhere in this codebase today --
`packages/data` has no bid/ask/depth concept, and
`packages/risk/engine.py`'s liquidity risk-check step already documents
this exact gap ("spread/orderbook depth check pending a real market data
provider"). Per §71's explicit constraint ("não depender exclusivamente de
order book"), this engine is built to work WITHOUT one: liquidity is
estimated from a volume percentile (computed by the caller across an
asset's same-asset-class peers -- see packages/market/universe.py) plus
data quality. `OrderBookSnapshot` is an optional, additive input: if a
future provider ever supplies real bid/ask/depth, `score_liquidity` folds
it in directly rather than needing a rewrite. Until then, every assessment
is honestly labeled `source="proxy"`.

This is deliberately NOT a duplicate of
`packages/quant/scoring/inputs.py::_liquidity_proxy` -- that function
scores one signal's current volume against its OWN recent average (a
per-signal input to OpportunityScore.liquidity). This module scores an
ASSET, independent of any signal, against its PEERS (an input to
`Asset.liquidity_score`/tiering, used for universe curation and paper-
eligibility -- §9-10, §67-70 -- before any signal exists).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

# -- closed vocabulary -- "PROMPT 11" §9 (LIQUIDITY TIERS) ---------------
TIER_A = "tier_a"
TIER_B = "tier_b"
TIER_C = "tier_c"
UNTRADABLE = "untradable"

LIQUIDITY_TIERS = (TIER_A, TIER_B, TIER_C, UNTRADABLE)

# Tier boundaries on the 0-100 composite score. Strategies should prefer
# TIER_A/TIER_B ("PROMPT 11" §10); TIER_C is usable but degraded; UNTRADABLE
# excludes the asset from the scanner entirely (see universe.py).
_TIER_A_MIN = 80.0
_TIER_B_MIN = 55.0
_TIER_C_MIN = 30.0


def tier_for_score(score: float) -> str:
    if score >= _TIER_A_MIN:
        return TIER_A
    if score >= _TIER_B_MIN:
        return TIER_B
    if score >= _TIER_C_MIN:
        return TIER_C
    return UNTRADABLE


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Optional real order-book input. No current provider supplies this
    -- the engine works fully without it (see module docstring)."""

    bid: float
    ask: float
    bid_depth: float
    ask_depth: float


@dataclass(frozen=True)
class LiquidityAssessment:
    symbol: str
    score: float  # 0-100
    tier: str
    source: str  # "proxy" | "orderbook"
    components: dict[str, float] = field(default_factory=dict)


def percentile_rank(value: float, population: Sequence[float]) -> float:
    """0-100 rank of `value` within `population` (inclusive). An empty
    population is an honest "no peer data" case -- returns a neutral 50.0
    rather than fabricating a rank.
    """
    if not population:
        return 50.0
    count_le = sum(1 for v in population if v <= value)
    return round(100.0 * count_le / len(population), 2)


def _spread_score(book: OrderBookSnapshot, max_spread_bps: float) -> float:
    mid = (book.bid + book.ask) / 2
    if mid <= 0 or max_spread_bps <= 0:
        return 0.0
    spread_bps = 10_000 * (book.ask - book.bid) / mid
    return max(0.0, min(100.0, 100.0 * (1 - spread_bps / max_spread_bps)))


def _depth_score(book: OrderBookSnapshot, min_depth_multiple: float, reference_size: float) -> float:
    if reference_size <= 0 or min_depth_multiple <= 0:
        return 100.0  # no reference trade size configured -- nothing to fall short of
    required = reference_size * min_depth_multiple
    available = min(book.bid_depth, book.ask_depth)
    return max(0.0, min(100.0, 100.0 * available / required))


def score_liquidity(
    *,
    symbol: str,
    volume_percentile: float,
    data_quality_score: float,
    orderbook: OrderBookSnapshot | None = None,
    max_spread_bps: float = 50.0,
    min_depth_multiple: float = 1.0,
    reference_size: float = 0.0,
) -> LiquidityAssessment:
    """Composite 0-100 liquidity score for one asset.

    `volume_percentile`/`data_quality_score` are always used (the
    proxy-only path). When `orderbook` is supplied, spread/depth
    components are folded in too -- reusing
    packages/risk/config.py::LiquidityConfig's max_spread_bps/
    min_orderbook_depth_multiple as the thresholds, same numbers the Risk
    Engine would use for a real spread/depth check.
    """
    components = {"volume_percentile": volume_percentile, "data_quality": data_quality_score}
    source = "proxy"
    if orderbook is not None:
        components["spread"] = _spread_score(orderbook, max_spread_bps)
        components["depth"] = _depth_score(orderbook, min_depth_multiple, reference_size)
        source = "orderbook"

    score = round(sum(components.values()) / len(components), 2)
    return LiquidityAssessment(symbol=symbol, score=score, tier=tier_for_score(score), source=source, components=components)
