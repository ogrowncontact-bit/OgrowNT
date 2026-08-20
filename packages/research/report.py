"""Research Report Generator — "PROMPT 10" §90-91's periodic human-facing
summary of everything the Autonomous Research Agent has done, is doing,
and is waiting on a human for.

Eleven sections, each a read over tables/functions this phase already
built — nothing here computes anything new, and nothing here has a side
effect on the database. Every section handles the empty case honestly
("no hypotheses proposed yet") rather than omitting itself or fabricating
placeholder content, the same "no hallucinated data" discipline as every
report in this codebase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.research import approval, budget
from packages.shared.models import DriftDetection, ResearchHypothesis, ResearchKnowledgeEdge, StrategyRow, StrategyVersion
from packages.shared.models import Experiment as ExperimentRow

RECENT_LIMIT = 10


@dataclass(frozen=True)
class ResearchReport:
    generated_at: datetime
    executive_summary: dict
    active_hypotheses: list[dict]
    recent_experiments: list[dict]
    degradation_and_drift_alerts: list[dict]
    feature_research_findings: dict
    strategy_versions: list[dict]
    knowledge_graph_highlights: list[dict]
    research_budget_usage: dict
    pending_approvals: list[dict]
    security_and_sandbox_posture: dict
    recommendations: list[str] = field(default_factory=list)


def _section_1_executive_summary(db: Session, hypotheses: list[ResearchHypothesis], experiments: list[ExperimentRow]) -> dict:
    open_hypotheses = sum(1 for h in hypotheses if h.status in ("proposed", "experimenting"))
    completed_experiments = sum(1 for e in experiments if e.status not in ("queued", "running"))
    promising_or_better = sum(1 for e in experiments if e.status in ("promising", "validating", "approved"))
    return {
        "total_hypotheses": len(hypotheses), "open_hypotheses": open_hypotheses,
        "total_experiments_recent_window": len(experiments), "completed_experiments_recent_window": completed_experiments,
        "promising_or_better_recent_window": promising_or_better,
    }


def _section_2_active_hypotheses(hypotheses: list[ResearchHypothesis]) -> list[dict]:
    active = [h for h in hypotheses if h.status in ("proposed", "approved", "experimenting")]
    return [
        {"id": h.id, "title": h.title, "status": h.status, "priority_score": h.priority_score, "source": h.source, "risk": h.risk}
        for h in sorted(active, key=lambda h: h.priority_score or 0.0, reverse=True)[:RECENT_LIMIT]
    ]


def _section_3_recent_experiments(experiments: list[ExperimentRow]) -> list[dict]:
    return [
        {
            "id": e.id, "type": e.type, "status": e.status,
            "strategy_code": (e.candidate or {}).get("strategy_code"),
            "changed_params": (e.result or {}).get("changed_params") if e.result else None,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in experiments[:RECENT_LIMIT]
    ]


def _section_4_degradation_and_drift(db: Session) -> list[dict]:
    rows = db.execute(select(DriftDetection).order_by(DriftDetection.ts.desc()).limit(RECENT_LIMIT)).scalars().all()
    return [
        {"drift_type": r.drift_type, "entity": r.entity, "severity": r.severity, "ts": r.ts.isoformat() if r.ts else None}
        for r in rows
    ]


def _section_5_feature_research(db: Session) -> dict:
    from packages.research.features import research_feature_signals  # local import: avoids a cycle risk with report imports growing over time

    signals = research_feature_signals(db)
    regime_dependent = sum(1 for s in signals if s.regime_dependent)
    return {
        "pattern_signals_with_evidence": len(signals), "regime_dependent_signals": regime_dependent,
        "top_signals": [
            {"pattern_type": s.pattern_type, "regime": s.regime, "expectancy": s.expectancy, "sample_size": s.sample_size}
            for s in sorted(signals, key=lambda s: s.expectancy or 0.0, reverse=True)[:5]
        ],
    }


def _section_6_strategy_versions(db: Session) -> list[dict]:
    versions = db.execute(select(StrategyVersion).order_by(StrategyVersion.created_at.desc()).limit(RECENT_LIMIT)).scalars().all()
    strategies = {s.id: s.code for s in db.execute(select(StrategyRow)).scalars().all()}
    return [
        {
            "id": v.id, "strategy_code": strategies.get(v.strategy_id), "version": v.version,
            "lifecycle_status": v.lifecycle_status, "validation_status": v.validation_status,
        }
        for v in versions
    ]


def _section_7_knowledge_graph(db: Session) -> list[dict]:
    edges = db.execute(select(ResearchKnowledgeEdge).order_by(ResearchKnowledgeEdge.confidence.desc()).limit(RECENT_LIMIT)).scalars().all()
    return [
        {"subject": e.subject, "relation": e.relation, "object": e.object, "confidence": e.confidence, "sample_size": e.sample_size}
        for e in edges
    ]


def _section_8_budget_usage(db: Session, *, now: datetime | None = None) -> dict:
    return {
        resource_type: {"used": status.used, "limit": status.limit, "exhausted": status.exhausted}
        for resource_type in budget.RESOURCE_TYPES
        for status in [budget.check_budget(db, resource_type=resource_type, now=now)]
    }


def _section_9_pending_approvals(db: Session) -> list[dict]:
    pending = approval.list_pending_approvals(db)
    return [
        {"id": a.id, "entity_type": a.entity_type, "entity_id": a.entity_id, "action": a.action, "created_at": a.created_at.isoformat() if a.created_at else None}
        for a in pending
    ]


def _section_10_security_posture() -> dict:
    return {
        "strategy_dsl": "whitelisted dict-based condition tree only (packages.research.dsl) -- no eval/exec/compile anywhere in the research pipeline",
        "self_execution_boundary": (
            "no module in packages/research or apps/research_worker can write strategies.params, positions, "
            "orders, or promote a StrategyVersion without a human-reviewed ResearchApproval (packages.research.approval)"
        ),
        "compute_isolation": "apps/research_worker is a separate process/queue from apps/worker (live trading) and apps/backtest_worker (operator-triggered Strategy Lab)",
        "budget_enforcement": "packages.research.budget.spend raises BudgetExceededError before any compute-costed research_queue job runs over its rolling-window cap",
    }


def _recommendations(hypotheses: list[ResearchHypothesis], experiments: list[ExperimentRow], pending_approvals: list[dict]) -> list[str]:
    recs = []
    if pending_approvals:
        recs.append(f"{len(pending_approvals)} research approval(s) awaiting human review -- see section 9.")
    promising = [e for e in experiments if e.status in ("promising", "validating")]
    if promising:
        recs.append(f"{len(promising)} experiment(s) show promising/validating results and may be worth an approval request.")
    if not hypotheses:
        recs.append("no hypotheses have been proposed yet -- the research loop has not had a trigger to act on.")
    if not recs:
        recs.append("nothing currently requires human attention.")
    return recs


def generate_research_report(db: Session, *, now: datetime | None = None, recent_limit: int = RECENT_LIMIT) -> ResearchReport:
    now = now or datetime.now(timezone.utc)
    hypotheses = list(db.execute(select(ResearchHypothesis).order_by(ResearchHypothesis.created_at.desc()).limit(50)).scalars().all())
    experiments = list(db.execute(select(ExperimentRow).order_by(ExperimentRow.created_at.desc()).limit(50)).scalars().all())
    pending_approvals = _section_9_pending_approvals(db)

    return ResearchReport(
        generated_at=now,
        executive_summary=_section_1_executive_summary(db, hypotheses, experiments),
        active_hypotheses=_section_2_active_hypotheses(hypotheses),
        recent_experiments=_section_3_recent_experiments(experiments),
        degradation_and_drift_alerts=_section_4_degradation_and_drift(db),
        feature_research_findings=_section_5_feature_research(db),
        strategy_versions=_section_6_strategy_versions(db),
        knowledge_graph_highlights=_section_7_knowledge_graph(db),
        research_budget_usage=_section_8_budget_usage(db, now=now),
        pending_approvals=pending_approvals,
        security_and_sandbox_posture=_section_10_security_posture(),
        recommendations=_recommendations(hypotheses, experiments, pending_approvals),
    )
