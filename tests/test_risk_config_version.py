"""packages/risk/config_version.py -- "PROMPT 12" §116-119: versioned,
audited risk-limit changes."""
from __future__ import annotations

from packages.risk.config_version import (
    ACTIVE,
    PENDING,
    SUPERSEDED,
    diff_versions,
    get_active_version,
    get_version,
    list_versions,
    record_config_version,
)


def test_first_recorded_version_starts_at_one_and_is_active(db_session):
    version = record_config_version(db_session, parameters={"loss_limits": {"max_daily_loss_pct": 3}}, reason="initial")
    assert version.version == 1
    assert version.status == ACTIVE


def test_versions_increment_and_previous_active_is_superseded(db_session):
    v1 = record_config_version(db_session, parameters={"a": 1}, reason="first")
    v2 = record_config_version(db_session, parameters={"a": 2}, reason="second")

    assert v2.version == v1.version + 1
    db_session.refresh(v1)
    assert v1.status == SUPERSEDED
    assert v2.status == ACTIVE


def test_get_active_version_returns_the_latest_active_one(db_session):
    record_config_version(db_session, parameters={"a": 1}, reason="first")
    latest = record_config_version(db_session, parameters={"a": 2}, reason="second")

    active = get_active_version(db_session)
    assert active is not None
    assert active.version == latest.version


def test_pending_status_does_not_supersede_the_active_version(db_session):
    active_version = record_config_version(db_session, parameters={"a": 1}, reason="active one")
    record_config_version(db_session, parameters={"a": 2}, reason="proposed change", status=PENDING)

    still_active = get_active_version(db_session)
    assert still_active is not None
    assert still_active.version == active_version.version


def test_list_versions_returns_newest_first(db_session):
    record_config_version(db_session, parameters={"a": 1}, reason="v1")
    record_config_version(db_session, parameters={"a": 2}, reason="v2")
    record_config_version(db_session, parameters={"a": 3}, reason="v3")

    versions = list_versions(db_session)
    assert [v.reason for v in versions[:3]] == ["v3", "v2", "v1"]


def test_get_version_by_number(db_session):
    v1 = record_config_version(db_session, parameters={"a": 1}, reason="first", approved_by="admin@example.com")
    found = get_version(db_session, v1.version)
    assert found is not None
    assert found.approved_by == "admin@example.com"


def test_get_version_missing_returns_none(db_session):
    assert get_version(db_session, 999999) is None


def test_diff_versions_flags_changed_nested_keys():
    old = {"loss_limits": {"max_daily_loss_pct": 3, "max_weekly_loss_pct": 6}, "leverage": {"max_leverage": 1.0}}
    new = {"loss_limits": {"max_daily_loss_pct": 2, "max_weekly_loss_pct": 6}, "leverage": {"max_leverage": 1.0}}

    diffs = diff_versions(old, new)
    assert len(diffs) == 1
    assert diffs[0].key == "loss_limits.max_daily_loss_pct"
    assert diffs[0].old_value == 3
    assert diffs[0].new_value == 2


def test_diff_versions_flags_added_and_removed_keys():
    old = {"a": {"x": 1}}
    new = {"a": {"x": 1, "y": 2}}

    diffs = diff_versions(old, new)
    assert len(diffs) == 1
    assert diffs[0].key == "a.y"
    assert diffs[0].old_value is None
    assert diffs[0].new_value == 2


def test_diff_versions_no_changes_is_empty():
    same = {"a": {"x": 1, "y": [1, 2, 3]}}
    assert diff_versions(same, dict(same)) == []
