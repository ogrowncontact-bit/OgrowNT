"""Portfolio Concentration Risk & Hidden Factor Exposure — "PROMPT 12".

Distinct from two existing, already-working correlation checks that this
module deliberately does NOT duplicate:
  - packages/risk/correlation_guard.py::check_correlation_guard -- a
    per-SIGNAL gate ("would adding THIS candidate breach the cluster
    limit"), run at trade time inside evaluate_signal().
  - packages/market/clustering.py::find_clusters -- clusters candidate
    OPPORTUNITIES (pending signals) for ranking-penalty purposes.

Neither answers "how concentrated is the book RIGHT NOW, across every
currently open position, independent of any new candidate" -- that is this
module's job, reusing find_clusters' union-find-over-the-correlation-
matrix algorithm rather than a second implementation of it (positions are
adapted into the same OpportunityCandidate shape it already accepts; the
`signal_id` slot is repurposed to hold a position id here -- the algorithm
only ever treats it as an opaque identifier, never dereferences it as an
actual Signal).

"Hidden factor exposure" here means the coarse asset_class concentration
already visible in the DB (Asset.asset_class) plus the correlation
clusters' own `factor` label (e.g. "crypto_correlation") -- there is no
fundamental factor model (PCA/regression-based factor loadings) anywhere
in this codebase, and fabricating one to sound more sophisticated than the
available data supports would violate this project's "no hallucinated
data" rule. See docs/capital-defense-engine.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.market.clustering import ClusterResult, OpportunityCandidate, find_clusters
from packages.risk.config import RiskLimits
from packages.shared.models import Asset, Position

LOW = "low"
MODERATE = "moderate"
HIGH = "high"
CONCENTRATED = "concentrated"

CONCENTRATION_STATES = (LOW, MODERATE, HIGH, CONCENTRATED)

# Same "70%/40% warning zone before the hard limit" convention already used
# by packages/risk/safety_belt.py (DEFENSIVE at 0.7x, CAUTION-adjacent
# checks at 0.7x) -- reused here rather than inventing new fractions.
_HIGH_FRACTION = 0.7
_MODERATE_FRACTION = 0.4

# A single asset class dominating this much of total exposure is flagged as
# a hidden factor concentration -- e.g. "everything is secretly one crypto
# bet" even when the individual positions look diversified by symbol.
_ASSET_CLASS_WARNING_FRACTION = 0.5


@dataclass(frozen=True)
class ConcentrationAssessment:
    open_position_count: int
    total_exposure_notional: float
    clusters: list[ClusterResult]
    max_cluster_exposure_pct: float  # % of equity in the single largest correlated cluster
    asset_class_exposure_pct: dict[str, float]  # asset_class -> % of total exposure notional
    concentration_state: str
    hidden_factor_warnings: list[str] = field(default_factory=list)


def _cluster_exposure_pct(cluster: ClusterResult, positions_by_asset: dict[int, Position], equity: float) -> float:
    if equity <= 0:
        return 0.0
    notional = sum(positions_by_asset[asset_id].entry_price * positions_by_asset[asset_id].size for asset_id in cluster.asset_ids)
    return notional / equity * 100


def _classify_state(max_cluster_exposure_pct: float, max_correlated_cluster_pct: float) -> str:
    if max_cluster_exposure_pct >= max_correlated_cluster_pct:
        return CONCENTRATED
    if max_cluster_exposure_pct >= max_correlated_cluster_pct * _HIGH_FRACTION:
        return HIGH
    if max_cluster_exposure_pct >= max_correlated_cluster_pct * _MODERATE_FRACTION:
        return MODERATE
    return LOW


def assess_concentration(db: Session, limits: RiskLimits, equity: float, *, timeframe: str = "1m") -> ConcentrationAssessment:
    open_positions = db.query(Position).filter(Position.status == "open").all()
    if not open_positions:
        return ConcentrationAssessment(
            open_position_count=0, total_exposure_notional=0.0, clusters=[], max_cluster_exposure_pct=0.0,
            asset_class_exposure_pct={}, concentration_state=LOW, hidden_factor_warnings=[],
        )

    positions_by_asset = {p.asset_id: p for p in open_positions}
    assets = {a.id: a for a in db.query(Asset).filter(Asset.id.in_(positions_by_asset.keys())).all()}

    candidates = [
        OpportunityCandidate(
            signal_id=position.id,  # repurposed: an opaque member id, not an actual Signal -- see module docstring
            asset_id=position.asset_id,
            symbol=assets[position.asset_id].symbol if position.asset_id in assets else str(position.asset_id),
            direction=position.direction,
            asset_class=assets[position.asset_id].asset_class if position.asset_id in assets else None,
        )
        for position in open_positions
    ]
    clusters = find_clusters(db, candidates, correlation_threshold=limits.portfolio.correlation_threshold)

    total_notional = sum(p.entry_price * p.size for p in open_positions)
    max_cluster_pct = max(
        (_cluster_exposure_pct(c, positions_by_asset, equity) for c in clusters), default=0.0,
    )

    asset_class_notional: dict[str, float] = {}
    for position in open_positions:
        asset_class = assets[position.asset_id].asset_class if position.asset_id in assets else "unknown"
        asset_class_notional[asset_class] = asset_class_notional.get(asset_class, 0.0) + position.entry_price * position.size
    asset_class_exposure_pct = {
        asset_class: round(notional / total_notional * 100, 4) if total_notional > 0 else 0.0
        for asset_class, notional in asset_class_notional.items()
    }

    warnings: list[str] = []
    for asset_class, pct in asset_class_exposure_pct.items():
        if pct / 100 >= _ASSET_CLASS_WARNING_FRACTION:
            warnings.append(f"{asset_class} accounts for {pct:.1f}% of open exposure -- concentrated hidden factor")
    for cluster in clusters:
        cluster_pct = _cluster_exposure_pct(cluster, positions_by_asset, equity)
        if cluster.factor is not None and cluster_pct >= limits.portfolio.max_correlated_cluster_pct * _HIGH_FRACTION:
            warnings.append(
                f"cluster of {len(cluster.asset_ids)} {cluster.direction} positions ({', '.join(cluster.symbols)}) "
                f"sharing factor '{cluster.factor}' is {cluster_pct:.1f}% of equity"
            )

    return ConcentrationAssessment(
        open_position_count=len(open_positions),
        total_exposure_notional=round(total_notional, 2),
        clusters=clusters,
        max_cluster_exposure_pct=round(max_cluster_pct, 4),
        asset_class_exposure_pct=asset_class_exposure_pct,
        concentration_state=_classify_state(max_cluster_pct, limits.portfolio.max_correlated_cluster_pct),
        hidden_factor_warnings=warnings,
    )
