"""Research Memory + Knowledge Graph — "PROMPT 10" §41-43."""
from __future__ import annotations

from datetime import datetime, timezone

from packages.research import knowledge
from packages.shared.models import Experiment


def test_upsert_creates_a_new_edge(db_session):
    edge = knowledge.upsert_edge(
        db_session, subject="momentum_v1", relation="not_improved_by", object_="roc_threshold",
        confidence=0.8, sample_size=10, evidence={"note": "first"},
    )
    assert edge.subject == "momentum_v1"
    assert edge.confidence == 0.8
    assert edge.sample_size == 10


def test_upsert_merges_repeat_evidence_into_one_row(db_session):
    first = knowledge.upsert_edge(
        db_session, subject="trend_following_v1", relation="improved_by", object_="entry_threshold",
        confidence=0.8, sample_size=10, evidence={"note": "first"},
    )
    second = knowledge.upsert_edge(
        db_session, subject="trend_following_v1", relation="improved_by", object_="entry_threshold",
        confidence=0.4, sample_size=10, evidence={"note": "second"},
    )
    assert second.id == first.id  # same row, not a duplicate
    assert second.confidence == 0.6  # sample-size-weighted average of 0.8 and 0.4
    assert second.sample_size == 20
    assert second.evidence["latest"]["note"] == "second"


def test_query_edges_filters_by_subject_relation_object(db_session):
    knowledge.upsert_edge(db_session, subject="a", relation="improved_by", object_="x", confidence=0.9, sample_size=5, evidence={})
    knowledge.upsert_edge(db_session, subject="b", relation="not_improved_by", object_="y", confidence=0.9, sample_size=5, evidence={})

    only_a = knowledge.query_edges(db_session, subject="a")
    assert len(only_a) == 1
    assert only_a[0].subject == "a"

    only_not_improved = knowledge.query_edges(db_session, relation="not_improved_by")
    assert all(e.relation == "not_improved_by" for e in only_not_improved)


def test_has_known_negative_result(db_session):
    assert knowledge.has_known_negative_result(db_session, subject="mean_reversion_v1", object_="rsi_oversold") is None
    knowledge.upsert_edge(
        db_session, subject="mean_reversion_v1", relation=knowledge.RELATION_NOT_IMPROVED_BY, object_="rsi_oversold",
        confidence=0.7, sample_size=15, evidence={},
    )
    found = knowledge.has_known_negative_result(db_session, subject="mean_reversion_v1", object_="rsi_oversold")
    assert found is not None
    assert found.relation == knowledge.RELATION_NOT_IMPROVED_BY


def _experiment(db_session, *, status: str, num_trades: int, quality_score: float, changed_params: list, strategy_code: str = "momentum_v1") -> Experiment:
    row = Experiment(
        hypothesis_id=None, type="backtest",
        control={"strategy_code": strategy_code, "params": {}},
        candidate={"strategy_code": strategy_code, "params": {"roc_threshold": 2.5}},
        dataset={}, parameters={}, status=status,
        result={
            "changed_params": changed_params,
            "candidate_report": {"num_trades": num_trades, "quality_score": quality_score},
            "reasons": ["test fixture"],
        },
        reproducibility={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_derive_edges_from_experiment_positive_status(db_session):
    experiment = _experiment(db_session, status="promising", num_trades=25, quality_score=80.0, changed_params=["roc_threshold"])
    edges = knowledge.derive_edges_from_experiment(db_session, experiment)
    assert len(edges) == 1
    assert edges[0].relation == knowledge.RELATION_IMPROVED_BY
    assert edges[0].subject == "momentum_v1"
    assert edges[0].confidence == 0.8


def test_derive_edges_from_experiment_negative_status(db_session):
    experiment = _experiment(db_session, status="rejected", num_trades=25, quality_score=20.0, changed_params=["roc_threshold"])
    edges = knowledge.derive_edges_from_experiment(db_session, experiment)
    assert len(edges) == 1
    assert edges[0].relation == knowledge.RELATION_NOT_IMPROVED_BY
    assert edges[0].confidence == 0.8  # 1 - 20/100


def test_derive_edges_from_experiment_zero_trades_produces_no_edge(db_session):
    """A zero-trade candidate is a data/period problem, not evidence about
    whether the changed parameters help -- never a 0-sample "fact"."""
    experiment = _experiment(db_session, status="failed", num_trades=0, quality_score=0.0, changed_params=["roc_threshold"])
    edges = knowledge.derive_edges_from_experiment(db_session, experiment)
    assert edges == []


def test_derive_edges_from_experiment_no_changed_params_produces_no_edge(db_session):
    experiment = _experiment(db_session, status="promising", num_trades=25, quality_score=80.0, changed_params=[])
    edges = knowledge.derive_edges_from_experiment(db_session, experiment)
    assert edges == []


def test_derive_edges_from_experiment_queued_status_produces_no_edge(db_session):
    experiment = _experiment(db_session, status="queued", num_trades=0, quality_score=0.0, changed_params=["x"])
    experiment.result = None
    db_session.commit()
    edges = knowledge.derive_edges_from_experiment(db_session, experiment)
    assert edges == []
