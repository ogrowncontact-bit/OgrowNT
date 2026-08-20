"""Human Approval Workflow + Audit Trail — "PROMPT 10" §64, §90-91."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.research import approval, versioning
from packages.shared.models import AuditLog, Experiment, ResearchHypothesis, StrategyRow


def _hypothesis(db_session, status="proposed") -> ResearchHypothesis:
    row = ResearchHypothesis(
        title="t", description="d", problem="p", observation="o", hypothesis="h", expected_effect="e",
        source="manual", status=status,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _strategy(db_session, code="approval_test_v1") -> StrategyRow:
    row = StrategyRow(code=code, name=code, family="test", version="1.0")
    db_session.add(row)
    db_session.commit()
    return row


def test_request_approval_rejects_unknown_entity_type_or_action(db_session):
    with pytest.raises(ValueError):
        approval.request_approval(db_session, entity_type="not_a_real_entity", entity_id=1, action="approve", evidence={})
    with pytest.raises(ValueError):
        approval.request_approval(db_session, entity_type="hypothesis", entity_id=1, action="not_a_real_action", evidence={})


def test_request_approval_creates_pending_row(db_session):
    hyp = _hypothesis(db_session)
    row = approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp.id, action="approve", evidence={"x": 1})
    assert row.status == approval.STATUS_PENDING
    assert row.reviewer is None


def test_record_decision_requires_non_empty_reviewer(db_session):
    hyp = _hypothesis(db_session)
    row = approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp.id, action="approve", evidence={})
    with pytest.raises(ValueError):
        approval.record_decision(db_session, row.id, decision="approved", reviewer="")


def test_record_decision_rejects_unknown_decision(db_session):
    hyp = _hypothesis(db_session)
    row = approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp.id, action="approve", evidence={})
    with pytest.raises(ValueError):
        approval.record_decision(db_session, row.id, decision="maybe", reviewer="tester@example.com")


def test_record_decision_cannot_be_applied_twice(db_session):
    hyp = _hypothesis(db_session)
    row = approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp.id, action="approve", evidence={})
    approval.record_decision(db_session, row.id, decision="approved", reviewer="tester@example.com")
    with pytest.raises(ValueError):
        approval.record_decision(db_session, row.id, decision="rejected", reviewer="tester@example.com")


def test_approving_a_hypothesis_flips_its_status(db_session):
    hyp = _hypothesis(db_session)
    row = approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp.id, action="approve", evidence={})
    approval.record_decision(db_session, row.id, decision="approved", reviewer="tester@example.com")
    refreshed = db_session.get(ResearchHypothesis, hyp.id)
    assert refreshed.status == "approved"


def test_rejecting_a_hypothesis_leaves_its_status_untouched(db_session):
    """Only APPROVED decisions apply a state change -- rejected/
    request_more_tests only update the ResearchApproval row itself."""
    hyp = _hypothesis(db_session)
    row = approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp.id, action="approve", evidence={})
    approval.record_decision(db_session, row.id, decision="rejected", reviewer="tester@example.com")
    refreshed = db_session.get(ResearchHypothesis, hyp.id)
    assert refreshed.status == "proposed"


def test_approving_a_promote_action_on_an_experimental_version_makes_it_a_challenger(db_session):
    strategy = _strategy(db_session)
    version = versioning.create_version(db_session, strategy_id=strategy.id, params={})
    row = approval.request_approval(db_session, entity_type="strategy_version", entity_id=version.id, action="promote", evidence={})
    approval.record_decision(db_session, row.id, decision="approved", reviewer="tester@example.com")
    refreshed = db_session.get(type(version), version.id)
    assert refreshed.lifecycle_status == versioning.LIFECYCLE_CHALLENGER


def test_approving_a_promote_action_on_a_challenger_makes_it_champion(db_session):
    strategy = _strategy(db_session)
    version = versioning.create_version(db_session, strategy_id=strategy.id, params={})
    versioning.promote_to_challenger(db_session, version.id, reviewer="setup@example.com")
    row = approval.request_approval(db_session, entity_type="strategy_version", entity_id=version.id, action="promote", evidence={})
    approval.record_decision(db_session, row.id, decision="approved", reviewer="tester@example.com")
    refreshed = db_session.get(type(version), version.id)
    assert refreshed.lifecycle_status == versioning.LIFECYCLE_CHAMPION


def test_approving_quarantine_action_quarantines_the_version(db_session):
    strategy = _strategy(db_session)
    version = versioning.create_version(db_session, strategy_id=strategy.id, params={})
    row = approval.request_approval(db_session, entity_type="strategy_version", entity_id=version.id, action="quarantine", evidence={}, detail="bug found")
    approval.record_decision(db_session, row.id, decision="approved", reviewer="tester@example.com")
    refreshed = db_session.get(type(version), version.id)
    assert refreshed.validation_status == "QUARANTINED"


def _experiment(db_session, *, strategy_code: str) -> Experiment:
    row = Experiment(
        hypothesis_id=None, type="backtest",
        control={"strategy_code": strategy_code, "params": {}},
        candidate={"strategy_code": strategy_code, "params": {"roc_threshold": 2.5}},
        dataset={}, parameters={}, status="promising",
        result={
            "changed_params": ["roc_threshold"],
            "candidate_report": {"num_trades": 30, "quality_score": 75.0, "quality_status": "PROMISING"},
        },
        reproducibility={}, created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_approving_promote_on_an_experiment_creates_a_new_strategy_version(db_session):
    strategy = _strategy(db_session, code="approval_experiment_v1")
    experiment = _experiment(db_session, strategy_code="approval_experiment_v1")
    row = approval.request_approval(db_session, entity_type="experiment", entity_id=experiment.id, action="promote", evidence={})
    approval.record_decision(db_session, row.id, decision="approved", reviewer="tester@example.com")

    from sqlalchemy import select

    from packages.shared.models import StrategyVersion

    versions = db_session.execute(select(StrategyVersion).where(StrategyVersion.strategy_id == strategy.id)).scalars().all()
    assert len(versions) == 1
    assert versions[0].params == {"roc_threshold": 2.5}
    assert versions[0].validation_status == "PROMISING"
    assert versions[0].lifecycle_status == versioning.LIFECYCLE_EXPERIMENTAL


def test_approving_promote_on_an_experiment_with_no_result_raises(db_session):
    row_exp = Experiment(
        hypothesis_id=None, type="backtest", control={"strategy_code": "x", "params": {}},
        candidate={"strategy_code": "x", "params": {}}, dataset={}, parameters={}, status="running",
        result=None, reproducibility={}, created_at=datetime.now(timezone.utc),
    )
    db_session.add(row_exp)
    db_session.commit()
    approval_row = approval.request_approval(db_session, entity_type="experiment", entity_id=row_exp.id, action="promote", evidence={})
    with pytest.raises(ValueError):
        approval.record_decision(db_session, approval_row.id, decision="approved", reviewer="tester@example.com")


def test_list_pending_approvals_excludes_resolved(db_session):
    hyp = _hypothesis(db_session)
    row1 = approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp.id, action="approve", evidence={})
    hyp2 = _hypothesis(db_session)
    row2 = approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp2.id, action="reject", evidence={})
    approval.record_decision(db_session, row1.id, decision="approved", reviewer="tester@example.com")

    pending = approval.list_pending_approvals(db_session)
    ids = {p.id for p in pending}
    assert row1.id not in ids
    assert row2.id in ids


def test_every_decision_writes_an_audit_log_row(db_session):
    hyp = _hypothesis(db_session)
    row = approval.request_approval(db_session, entity_type="hypothesis", entity_id=hyp.id, action="approve", evidence={})
    approval.record_decision(db_session, row.id, decision="approved", reviewer="auditor@example.com")

    from sqlalchemy import select

    logs = db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "hypothesis", AuditLog.entity_id == hyp.id)
    ).scalars().all()
    assert any(log.action == "research_approval_approved" for log in logs)
    assert all(log.actor == "auditor@example.com" for log in logs)
