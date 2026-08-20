"""Research Memory + Knowledge Graph — "PROMPT 10" §41-43.

`ResearchKnowledgeEdge` is a simple (subject, relation, object) graph --
e.g. `("momentum_v1", "not_improved_by", "roc_threshold")` -- accumulated
automatically from `Experiment` results rather than requiring a human to
hand-curate it. `upsert_edge` merges repeat evidence into ONE row per
(subject, relation, object) triple (sample-size-weighted confidence)
instead of appending duplicate facts every time the same thing gets
re-tested.

False Signal Memory (§41, per this module's original design note: a query
function, not a new table) is `has_known_negative_result` below -- a
lookup against the same knowledge graph, so "don't repeat known-failed
research" doesn't need its own separate store beyond what the graph
already records.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.shared.models import Experiment as ExperimentRow
from packages.shared.models import ResearchKnowledgeEdge

RELATION_IMPROVED_BY = "improved_by"
RELATION_NOT_IMPROVED_BY = "not_improved_by"
POSITIVE_EXPERIMENT_STATUSES = ("promising", "validating", "approved")
NEGATIVE_EXPERIMENT_STATUSES = ("rejected", "quarantined", "failed")


def upsert_edge(
    db: Session, *, subject: str, relation: str, object_: str, confidence: float, sample_size: int,
    evidence: dict, source_experiment_id: int | None = None,
) -> ResearchKnowledgeEdge:
    """Merges into an existing (subject, relation, object) edge — sample-
    size-weighted confidence, accumulated sample_size — rather than ever
    inserting a duplicate fact."""
    existing = (
        db.execute(
            select(ResearchKnowledgeEdge).where(
                ResearchKnowledgeEdge.subject == subject, ResearchKnowledgeEdge.relation == relation,
                ResearchKnowledgeEdge.object == object_,
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        total_n = existing.sample_size + sample_size
        if total_n > 0:
            existing.confidence = round((existing.confidence * existing.sample_size + confidence * sample_size) / total_n, 4)
        existing.sample_size = total_n
        existing.evidence = {**existing.evidence, "latest": evidence}
        if source_experiment_id is not None:
            existing.source_experiment_id = source_experiment_id
        db.commit()
        return existing

    edge = ResearchKnowledgeEdge(
        subject=subject, relation=relation, object=object_, confidence=round(confidence, 4), sample_size=sample_size,
        evidence=evidence, source_experiment_id=source_experiment_id,
    )
    db.add(edge)
    db.commit()
    return edge


def query_edges(db: Session, *, subject: str | None = None, relation: str | None = None, object_: str | None = None) -> list[ResearchKnowledgeEdge]:
    stmt = select(ResearchKnowledgeEdge)
    if subject is not None:
        stmt = stmt.where(ResearchKnowledgeEdge.subject == subject)
    if relation is not None:
        stmt = stmt.where(ResearchKnowledgeEdge.relation == relation)
    if object_ is not None:
        stmt = stmt.where(ResearchKnowledgeEdge.object == object_)
    return list(db.execute(stmt.order_by(ResearchKnowledgeEdge.confidence.desc())).scalars().all())


def has_known_negative_result(db: Session, *, subject: str, object_: str) -> ResearchKnowledgeEdge | None:
    """§41's dedup principle applied to the knowledge graph: has this exact
    change already been tried on `subject` and found NOT to help? Callers
    (e.g. the not-yet-built research orchestration loop) use this to skip
    re-proposing a change the graph already has evidence against."""
    return (
        db.execute(
            select(ResearchKnowledgeEdge).where(
                ResearchKnowledgeEdge.subject == subject, ResearchKnowledgeEdge.relation == RELATION_NOT_IMPROVED_BY,
                ResearchKnowledgeEdge.object == object_,
            )
        )
        .scalars()
        .first()
    )


def derive_edges_from_experiment(db: Session, experiment: ExperimentRow) -> list[ResearchKnowledgeEdge]:
    """Turns one completed `Experiment` into durable knowledge-graph
    evidence: `subject` is the candidate's strategy_code, `object` is the
    sorted set of parameters that changed, `relation` is improved_by /
    not_improved_by depending on the §20 status classification, and
    `confidence` is drawn from the candidate's own quality_score -- no
    number here is invented independently of what the Experiment Engine
    already computed.
    """
    if experiment.result is None or experiment.status not in (*POSITIVE_EXPERIMENT_STATUSES, *NEGATIVE_EXPERIMENT_STATUSES):
        return []

    result = experiment.result
    changed = result.get("changed_params") or []
    candidate_report = result.get("candidate_report") or {}
    strategy_code = (experiment.candidate or {}).get("strategy_code")
    if not changed or not strategy_code:
        return []

    num_trades = int(candidate_report.get("num_trades") or 0)
    if num_trades == 0:
        # A zero-trade candidate is a data/period problem, not evidence
        # about whether the changed parameters help or hurt -- recording
        # it either way would pollute the graph with a 0-sample "fact".
        return []

    object_ = ",".join(sorted(changed))
    quality_score = float(candidate_report.get("quality_score") or 0.0)

    if experiment.status in POSITIVE_EXPERIMENT_STATUSES:
        relation, confidence = RELATION_IMPROVED_BY, min(1.0, max(0.0, quality_score / 100.0))
    else:
        relation, confidence = RELATION_NOT_IMPROVED_BY, min(1.0, max(0.0, 1.0 - quality_score / 100.0))

    edge = upsert_edge(
        db, subject=strategy_code, relation=relation, object_=object_, confidence=confidence, sample_size=num_trades,
        evidence={"experiment_id": experiment.id, "status": experiment.status, "reasons": result.get("reasons", [])},
        source_experiment_id=experiment.id,
    )
    return [edge]
