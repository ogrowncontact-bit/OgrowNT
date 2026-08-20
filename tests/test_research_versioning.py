"""Strategy Versioning + Champion/Challenger — "PROMPT 10" §26-33, §64."""
from __future__ import annotations

import pytest

from packages.research import versioning
from packages.shared.models import AuditLog, StrategyRow


def _strategy(db_session, code: str = "versioning_test_v1") -> StrategyRow:
    row = StrategyRow(code=code, name=code, family="test", version="1.0")
    db_session.add(row)
    db_session.commit()
    return row


def test_create_version_auto_increments_labels(db_session):
    strategy = _strategy(db_session)
    v1 = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 1})
    v2 = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 2}, parent_version_id=v1.id)
    assert v1.version == "v1"
    assert v2.version == "v2"
    assert v2.parent_version_id == v1.id
    assert v1.lifecycle_status == versioning.LIFECYCLE_EXPERIMENTAL
    assert v1.validation_status == "EXPERIMENTAL"


def test_create_version_unknown_strategy_raises(db_session):
    with pytest.raises(ValueError):
        versioning.create_version(db_session, strategy_id=999999, params={})


def test_create_version_rejects_invalid_statuses(db_session):
    strategy = _strategy(db_session)
    with pytest.raises(ValueError):
        versioning.create_version(db_session, strategy_id=strategy.id, params={}, validation_status="NOT_A_REAL_STATUS")
    with pytest.raises(ValueError):
        versioning.create_version(db_session, strategy_id=strategy.id, params={}, lifecycle_status="not_a_real_lifecycle")


def test_promote_to_challenger_requires_experimental_source(db_session):
    strategy = _strategy(db_session)
    version = versioning.create_version(db_session, strategy_id=strategy.id, params={})
    challenger = versioning.promote_to_challenger(db_session, version.id, reviewer="tester@example.com")
    assert challenger.lifecycle_status == versioning.LIFECYCLE_CHALLENGER

    with pytest.raises(ValueError):
        versioning.promote_to_challenger(db_session, challenger.id, reviewer="tester@example.com")  # already promoted


def test_all_state_transitions_require_a_non_empty_reviewer(db_session):
    strategy = _strategy(db_session)
    version = versioning.create_version(db_session, strategy_id=strategy.id, params={})
    for reviewer in ("", "   "):
        with pytest.raises(ValueError):
            versioning.promote_to_challenger(db_session, version.id, reviewer=reviewer)
        with pytest.raises(ValueError):
            versioning.retire(db_session, version.id, reviewer=reviewer)
        with pytest.raises(ValueError):
            versioning.quarantine_version(db_session, version.id, reviewer=reviewer, reason="x")


def test_promote_to_champion_retires_the_previous_champion(db_session):
    strategy = _strategy(db_session)
    v1 = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 1})
    versioning.promote_to_challenger(db_session, v1.id, reviewer="tester@example.com")
    versioning.promote_to_champion(db_session, v1.id, reviewer="tester@example.com")

    v2 = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 2}, parent_version_id=v1.id)
    versioning.promote_to_challenger(db_session, v2.id, reviewer="tester@example.com")
    versioning.promote_to_champion(db_session, v2.id, reviewer="tester@example.com")

    refreshed_v1 = db_session.get(type(v1), v1.id)
    assert refreshed_v1.lifecycle_status == versioning.LIFECYCLE_RETIRED
    assert versioning.get_champion(db_session, strategy.id).id == v2.id


def test_at_most_one_champion_ever(db_session):
    strategy = _strategy(db_session)
    versions = []
    for i in range(3):
        v = versioning.create_version(db_session, strategy_id=strategy.id, params={"i": i})
        versioning.promote_to_challenger(db_session, v.id, reviewer="tester@example.com")
        versioning.promote_to_champion(db_session, v.id, reviewer="tester@example.com")
        versions.append(v)

    from sqlalchemy import select

    from packages.shared.models import StrategyVersion

    champions = db_session.execute(
        select(StrategyVersion).where(StrategyVersion.strategy_id == strategy.id, StrategyVersion.lifecycle_status == versioning.LIFECYCLE_CHAMPION)
    ).scalars().all()
    assert len(champions) == 1
    assert champions[0].id == versions[-1].id


def test_rollback_restores_the_prior_champion(db_session):
    strategy = _strategy(db_session)
    v1 = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 1})
    versioning.promote_to_challenger(db_session, v1.id, reviewer="tester@example.com")
    versioning.promote_to_champion(db_session, v1.id, reviewer="tester@example.com")

    v2 = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 2}, parent_version_id=v1.id)
    versioning.promote_to_challenger(db_session, v2.id, reviewer="tester@example.com")
    versioning.promote_to_champion(db_session, v2.id, reviewer="tester@example.com")

    restored = versioning.rollback(db_session, strategy.id, reviewer="tester@example.com")
    assert restored.id == v1.id
    assert restored.lifecycle_status == versioning.LIFECYCLE_CHAMPION

    refreshed_v2 = db_session.get(type(v2), v2.id)
    assert refreshed_v2.lifecycle_status == versioning.LIFECYCLE_ROLLED_BACK


def test_rollback_with_no_champion_raises(db_session):
    strategy = _strategy(db_session)
    with pytest.raises(ValueError):
        versioning.rollback(db_session, strategy.id, reviewer="tester@example.com")


def test_quarantine_forces_retirement_of_champion(db_session):
    strategy = _strategy(db_session)
    v1 = versioning.create_version(db_session, strategy_id=strategy.id, params={})
    versioning.promote_to_challenger(db_session, v1.id, reviewer="tester@example.com")
    versioning.promote_to_champion(db_session, v1.id, reviewer="tester@example.com")

    quarantined = versioning.quarantine_version(db_session, v1.id, reviewer="tester@example.com", reason="found a critical bug")
    assert quarantined.validation_status == "QUARANTINED"
    assert quarantined.lifecycle_status == versioning.LIFECYCLE_RETIRED


def test_get_lineage_walks_parent_chain_oldest_first(db_session):
    strategy = _strategy(db_session)
    v1 = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 1})
    v2 = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 2}, parent_version_id=v1.id)
    v3 = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 3}, parent_version_id=v2.id)

    lineage = versioning.get_lineage(db_session, v3.id)
    assert [v.id for v in lineage] == [v1.id, v2.id, v3.id]


def test_every_state_transition_writes_an_audit_log_row(db_session):
    strategy = _strategy(db_session)
    v1 = versioning.create_version(db_session, strategy_id=strategy.id, params={})
    versioning.promote_to_challenger(db_session, v1.id, reviewer="auditor@example.com")

    from sqlalchemy import select

    rows = db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "strategy_version", AuditLog.entity_id == v1.id)
    ).scalars().all()
    actions = {r.action for r in rows}
    assert "create_strategy_version" in actions
    assert "promote_to_challenger" in actions
    assert all(r.actor for r in rows)


def test_compare_champion_challenger_honest_when_no_performance_yet(db_session):
    strategy = _strategy(db_session)
    champion = versioning.create_version(db_session, strategy_id=strategy.id, params={})
    challenger = versioning.create_version(db_session, strategy_id=strategy.id, params={"a": 1})
    comparison = versioning.compare_champion_challenger(champion, challenger)
    assert comparison["comparable"] is False
