"""Opportunity Clustering -- "PROMPT 11" §33-35."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.market.clustering import OpportunityCandidate, find_clusters, persist_clusters
from packages.shared.models import Asset, CorrelationMatrixEntry, OpportunityCluster

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def _asset(db_session, symbol: str, asset_class: str = "crypto") -> Asset:
    asset = Asset(symbol=symbol, asset_class=asset_class)
    db_session.add(asset)
    db_session.commit()
    return asset


def _corr(db_session, a: Asset, b: Asset, value: float) -> None:
    db_session.add(CorrelationMatrixEntry(ts=_NOW, asset_id_a=a.id, asset_id_b=b.id, window_days=30, correlation=value))
    db_session.commit()


def test_find_clusters_groups_strongly_correlated_same_direction_candidates(db_session):
    btc = _asset(db_session, "CLUSTER_BTC")
    eth = _asset(db_session, "CLUSTER_ETH")
    sol = _asset(db_session, "CLUSTER_SOL")
    _corr(db_session, btc, eth, 0.9)
    _corr(db_session, eth, sol, 0.85)
    # No direct BTC-SOL entry -- transitivity through ETH must still cluster them.

    candidates = [
        OpportunityCandidate(signal_id=1, asset_id=btc.id, symbol=btc.symbol, direction="long", asset_class="crypto"),
        OpportunityCandidate(signal_id=2, asset_id=eth.id, symbol=eth.symbol, direction="long", asset_class="crypto"),
        OpportunityCandidate(signal_id=3, asset_id=sol.id, symbol=sol.symbol, direction="long", asset_class="crypto"),
    ]
    clusters = find_clusters(db_session, candidates, correlation_threshold=0.7)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert set(cluster.symbols) == {"CLUSTER_BTC", "CLUSTER_ETH", "CLUSTER_SOL"}
    assert cluster.direction == "long"
    assert cluster.factor == "crypto_correlation"
    assert cluster.ranking_penalty > 0.0


def test_find_clusters_ignores_pairs_below_threshold(db_session):
    a = _asset(db_session, "CLUSTER_WEAK_A")
    b = _asset(db_session, "CLUSTER_WEAK_B")
    _corr(db_session, a, b, 0.2)

    candidates = [
        OpportunityCandidate(signal_id=1, asset_id=a.id, symbol=a.symbol, direction="long"),
        OpportunityCandidate(signal_id=2, asset_id=b.id, symbol=b.symbol, direction="long"),
    ]
    clusters = find_clusters(db_session, candidates, correlation_threshold=0.7)
    assert clusters == []


def test_find_clusters_only_groups_same_direction_candidates(db_session):
    a = _asset(db_session, "CLUSTER_DIR_A")
    b = _asset(db_session, "CLUSTER_DIR_B")
    _corr(db_session, a, b, 0.95)

    candidates = [
        OpportunityCandidate(signal_id=1, asset_id=a.id, symbol=a.symbol, direction="long"),
        OpportunityCandidate(signal_id=2, asset_id=b.id, symbol=b.symbol, direction="short"),
    ]
    clusters = find_clusters(db_session, candidates, correlation_threshold=0.7)
    assert clusters == []


def test_find_clusters_factor_is_none_for_mixed_asset_classes(db_session):
    a = _asset(db_session, "CLUSTER_MIX_A", asset_class="crypto")
    b = _asset(db_session, "CLUSTER_MIX_B", asset_class="index")
    _corr(db_session, a, b, 0.8)

    candidates = [
        OpportunityCandidate(signal_id=1, asset_id=a.id, symbol=a.symbol, direction="long", asset_class="crypto"),
        OpportunityCandidate(signal_id=2, asset_id=b.id, symbol=b.symbol, direction="long", asset_class="index"),
    ]
    clusters = find_clusters(db_session, candidates, correlation_threshold=0.7)
    assert len(clusters) == 1
    assert clusters[0].factor is None


def test_persist_clusters_writes_rows(db_session):
    a = _asset(db_session, "CLUSTER_PERSIST_A")
    b = _asset(db_session, "CLUSTER_PERSIST_B")
    _corr(db_session, a, b, 0.9)
    candidates = [
        OpportunityCandidate(signal_id=1, asset_id=a.id, symbol=a.symbol, direction="long"),
        OpportunityCandidate(signal_id=2, asset_id=b.id, symbol=b.symbol, direction="long"),
    ]
    clusters = find_clusters(db_session, candidates, correlation_threshold=0.7)
    written = persist_clusters(db_session, clusters, now=_NOW)
    assert written == 1
    row = db_session.query(OpportunityCluster).one()
    assert set(row.asset_ids) == {a.id, b.id}
    assert row.direction == "long"


def test_persist_clusters_no_op_with_empty_list(db_session):
    written = persist_clusters(db_session, [], now=_NOW)
    assert written == 0
    assert db_session.query(OpportunityCluster).count() == 0
