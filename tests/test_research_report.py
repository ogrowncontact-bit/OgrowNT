"""Research Report Generator — "PROMPT 10" §90-91."""
from __future__ import annotations

from dataclasses import asdict

from packages.research.report import generate_research_report
from packages.shared.models import ResearchHypothesis


def test_generate_research_report_has_exactly_eleven_sections_plus_timestamp(db_session):
    report = generate_research_report(db_session)
    d = asdict(report)
    assert set(d.keys()) == {
        "generated_at", "executive_summary", "active_hypotheses", "recent_experiments",
        "degradation_and_drift_alerts", "feature_research_findings", "strategy_versions",
        "knowledge_graph_highlights", "research_budget_usage", "pending_approvals",
        "security_and_sandbox_posture", "recommendations",
    }


def test_generate_research_report_is_honest_when_empty(db_session):
    report = generate_research_report(db_session)
    assert report.executive_summary["total_hypotheses"] == 0
    assert report.active_hypotheses == []
    assert report.recent_experiments == []
    assert report.degradation_and_drift_alerts == []
    assert report.knowledge_graph_highlights == []
    assert report.pending_approvals == []
    assert any("no hypotheses" in r for r in report.recommendations)


def test_generate_research_report_reflects_real_data(db_session):
    db_session.add(
        ResearchHypothesis(
            title="t", description="d", problem="p", observation="o", hypothesis="h", expected_effect="e",
            source="manual", status="proposed", priority_score=70.0,
        )
    )
    db_session.commit()
    report = generate_research_report(db_session)
    assert report.executive_summary["total_hypotheses"] == 1
    assert len(report.active_hypotheses) == 1
    assert report.active_hypotheses[0]["title"] == "t"


def test_generate_research_report_budget_section_covers_every_resource_type(db_session):
    from packages.research import budget

    report = generate_research_report(db_session)
    assert set(report.research_budget_usage.keys()) == set(budget.RESOURCE_TYPES)


def test_generate_research_report_security_posture_mentions_the_boundary(db_session):
    report = generate_research_report(db_session)
    text = " ".join(report.security_and_sandbox_posture.values())
    assert "human-reviewed" in text or "ResearchApproval" in text


def test_generate_research_report_recommends_pending_approvals_first(db_session):
    from packages.research import approval

    hyp = ResearchHypothesis(
        title="t", description="d", problem="p", observation="o", hypothesis="h", expected_effect="e",
        source="manual", status="proposed",
    )
    db_session.add(hyp)
    db_session.commit()
    approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp.id, action="approve", evidence={})

    report = generate_research_report(db_session)
    assert len(report.pending_approvals) == 1
    assert "awaiting human review" in report.recommendations[0]
