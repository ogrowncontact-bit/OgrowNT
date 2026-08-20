"""Opportunity Clustering -- "PROMPT 11" §33-35.

Reuses packages/risk/correlation_guard.py's persisted correlation matrix
(refresh_correlation_matrix, already run periodically by apps/worker) --
no new correlation computation happens here. A cluster is evidence of a
shared risk factor (e.g. BTC/ETH/SOL longs all being one crypto-beta bet),
never a claim of a causal relationship between the assets (§34: "evidence,
não garantias causais").
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.risk.config import load_risk_limits
from packages.shared.models import CorrelationMatrixEntry, OpportunityCluster


@dataclass(frozen=True)
class OpportunityCandidate:
    signal_id: int
    asset_id: int
    symbol: str
    direction: str  # "long" | "short"
    asset_class: str | None = None


@dataclass(frozen=True)
class ClusterResult:
    signal_ids: tuple[int, ...]
    asset_ids: tuple[int, ...]
    symbols: tuple[str, ...]
    direction: str
    factor: str | None
    avg_correlation: float
    combined_risk: float
    ranking_penalty: float


class _UnionFind:
    def __init__(self, items: list[int]) -> None:
        self._parent = {item: item for item in items}

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_a] = root_b


def _latest_correlation_pairs(db: Session, asset_ids: list[int]) -> dict[tuple[int, int], float]:
    """Most recent correlation for every pair among `asset_ids`, keyed by a
    sorted (min_id, max_id) tuple. Reads CorrelationMatrixEntry -- never
    recomputes.
    """
    if len(asset_ids) < 2:
        return {}
    rows = (
        db.query(CorrelationMatrixEntry)
        .filter(CorrelationMatrixEntry.asset_id_a.in_(asset_ids), CorrelationMatrixEntry.asset_id_b.in_(asset_ids))
        .order_by(CorrelationMatrixEntry.ts.desc())
        .all()
    )
    pairs: dict[tuple[int, int], float] = {}
    for row in rows:
        key = (min(row.asset_id_a, row.asset_id_b), max(row.asset_id_a, row.asset_id_b))
        pairs.setdefault(key, row.correlation)  # first row per pair is the most recent, thanks to the ORDER BY
    return pairs


def find_clusters(
    db: Session, candidates: list[OpportunityCandidate], *, correlation_threshold: float | None = None,
) -> list[ClusterResult]:
    """Groups same-direction candidates into connected components linked by
    |correlation| >= threshold (packages/risk/config.py's
    portfolio.correlation_threshold by default -- the same bar the Risk
    Engine's own Correlation Guard uses). Singletons (no correlated peer)
    are not reported: a cluster needs at least 2 members to mean anything.
    """
    threshold = (
        correlation_threshold if correlation_threshold is not None
        else load_risk_limits().portfolio.correlation_threshold
    )
    by_direction: dict[str, list[OpportunityCandidate]] = {}
    for candidate in candidates:
        by_direction.setdefault(candidate.direction, []).append(candidate)

    results: list[ClusterResult] = []
    for direction, group in by_direction.items():
        asset_ids = [c.asset_id for c in group]
        pairs = _latest_correlation_pairs(db, asset_ids)

        uf = _UnionFind(asset_ids)
        edge_correlations: dict[tuple[int, int], float] = {}
        for (a, b), corr in pairs.items():
            if abs(corr) >= threshold:
                uf.union(a, b)
                edge_correlations[(a, b)] = corr

        components: dict[int, list[OpportunityCandidate]] = {}
        for candidate in group:
            root = uf.find(candidate.asset_id)
            components.setdefault(root, []).append(candidate)

        for members in components.values():
            if len(members) < 2:
                continue
            member_ids = {m.asset_id for m in members}
            relevant = [corr for (a, b), corr in edge_correlations.items() if a in member_ids and b in member_ids]
            avg_corr = sum(abs(c) for c in relevant) / len(relevant) if relevant else 0.0
            asset_classes = {m.asset_class for m in members if m.asset_class is not None}
            factor = f"{next(iter(asset_classes))}_correlation" if len(asset_classes) == 1 else None
            # Larger clusters and stronger internal correlation both mean
            # more concentrated (less diversified) exposure -- both scale
            # the penalty, capped at 1.0 (a full attractiveness discount).
            ranking_penalty = min(1.0, (len(members) - 1) * avg_corr * 0.15)
            results.append(
                ClusterResult(
                    signal_ids=tuple(m.signal_id for m in members), asset_ids=tuple(m.asset_id for m in members),
                    symbols=tuple(m.symbol for m in members), direction=direction, factor=factor,
                    avg_correlation=round(avg_corr, 4), combined_risk=round(avg_corr, 4),
                    ranking_penalty=round(ranking_penalty, 4),
                )
            )
    return results


def persist_clusters(db: Session, clusters: list[ClusterResult], *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    for cluster in clusters:
        db.add(
            OpportunityCluster(
                ts=now, signal_ids=list(cluster.signal_ids), asset_ids=list(cluster.asset_ids),
                direction=cluster.direction, factor=cluster.factor, avg_correlation=cluster.avg_correlation,
                combined_risk=cluster.combined_risk, ranking_penalty=cluster.ranking_penalty,
            )
        )
    if clusters:
        db.commit()
    return len(clusters)
