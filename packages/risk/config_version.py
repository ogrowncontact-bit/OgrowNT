"""Risk Config Version & Audit Trail — "PROMPT 12" §116-119.

Every change to a live-tunable risk limit (config/risk_limits.yaml) must
be versioned and auditable — not a silent in-place file edit.
apps/api/routers/system.py's existing `PATCH /api/system/risk-limits`
("PROMPT 4") owns the actual file write; this module is the
versioning/audit layer a later task wires that endpoint to call alongside
it, not a replacement for it.

`parameters` on each row is the FULL resolved config snapshot after the
change, not just a diff, so any past version can be inspected or restored
on its own without replaying history from version 1. `diff_versions()` is
provided for callers (an audit-trail API/dashboard view) that want to show
only what changed between two versions, computed on demand rather than
stored twice.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.shared.models import RiskConfigVersion

PENDING = "pending"
APPROVED = "approved"
ACTIVE = "active"
SUPERSEDED = "superseded"
REJECTED = "rejected"


def get_active_version(db: Session) -> RiskConfigVersion | None:
    return (
        db.query(RiskConfigVersion)
        .filter(RiskConfigVersion.status == ACTIVE)
        .order_by(RiskConfigVersion.version.desc())
        .first()
    )


def list_versions(db: Session, *, limit: int = 50) -> list[RiskConfigVersion]:
    return db.query(RiskConfigVersion).order_by(RiskConfigVersion.version.desc()).limit(limit).all()


def get_version(db: Session, version: int) -> RiskConfigVersion | None:
    return db.query(RiskConfigVersion).filter(RiskConfigVersion.version == version).one_or_none()


def _next_version_number(db: Session) -> int:
    current_max = db.execute(select(func.max(RiskConfigVersion.version))).scalar_one_or_none()
    return (current_max or 0) + 1


def record_config_version(
    db: Session, *, parameters: dict, reason: str, approved_by: str | None = None, status: str = ACTIVE,
) -> RiskConfigVersion:
    """Records a new version. When status=ACTIVE (the default — a change
    already applied to the live config file), any PREVIOUSLY active
    version is marked SUPERSEDED first, so exactly one version is ever
    ACTIVE at a time — get_active_version() never has to pick among
    several.
    """
    if status == ACTIVE:
        previous_active = get_active_version(db)
        if previous_active is not None:
            previous_active.status = SUPERSEDED
            db.add(previous_active)

    version = RiskConfigVersion(
        version=_next_version_number(db), created_at=datetime.now(timezone.utc), approved_by=approved_by,
        parameters=parameters, reason=reason, status=status,
    )
    db.add(version)
    db.commit()
    return version


@dataclass(frozen=True)
class ConfigDiff:
    key: str
    old_value: Any
    new_value: Any


def _flatten(d: dict, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, full_key))
        else:
            flat[full_key] = value
    return flat


def diff_versions(old_parameters: dict, new_parameters: dict) -> list[ConfigDiff]:
    """Flat dotted-key diff between two config snapshots (e.g.
    "loss_limits.max_daily_loss_pct") — computed on demand, not stored, so
    the audit trail never has two competing sources of truth for "what
    changed"."""
    old_flat = _flatten(old_parameters)
    new_flat = _flatten(new_parameters)
    keys = sorted(set(old_flat) | set(new_flat))
    diffs = []
    for key in keys:
        old_value = old_flat.get(key)
        new_value = new_flat.get(key)
        if old_value != new_value:
            diffs.append(ConfigDiff(key=key, old_value=old_value, new_value=new_value))
    return diffs
