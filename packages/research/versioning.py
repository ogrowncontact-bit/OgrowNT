"""Strategy Versioning + Champion/Challenger + Shadow Mode — "PROMPT 10"
§26-33, §64.

`StrategyVersion` is an axis ORTHOGONAL to `StrategyRow.lifecycle_stage`
(Phase 2's idea/backtest/.../production capital-tier ladder, untouched
here): many versions per `strategy_id`, each tracking its own
`lifecycle_status` (experimental/challenger/champion/production_candidate/
rolled_back/retired) and `validation_status` (the exact closed vocabulary
`packages.backtest.quality_score.STATUS_LABELS` already defines).

§64 — "NO AUTOMATIC PRODUCTION PROMOTION... a promoção final deve
permanecer manual" — is enforced structurally, not by convention: every
state-changing function below requires a non-empty `reviewer` string and
writes an `AuditLog` row, the same actor-accountability pattern
`packages/agents/reliability.py::restore_from_quarantine` already uses for
admin-gated agent restores. Nothing in this module is ever called from
inside the research/generation pipeline itself — only from a human-
initiated API call.

Shadow Mode (§31) is scoped for what this system actually is — a single-
user, paper-trading-only system with no live capital at risk anywhere.
Rather than building a second, parallel signal-generation-and-tracking
pipeline inside `apps/worker` (a large, genuinely new execution path this
prompt's own §57 "self-improvement != self-execution" constraint argues
against), shadow-testing a challenger here means re-running
`packages.research.experiment.run_experiment` with the champion as control
and the challenger as candidate over the most recent real market data --
the exact same evidence a live shadow deployment would produce, through
the Experiment Engine already built and verified in this phase, with zero
new infrastructure and zero risk of ever touching a live signal path.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.backtest.quality_score import STATUS_LABELS
from packages.research.experiment import ArmSpec, ExperimentRow, run_experiment
from packages.risk.config import RiskLimits
from packages.shared.models import Asset, AuditLog, StrategyRow, StrategyVersion

LIFECYCLE_EXPERIMENTAL = "experimental"
LIFECYCLE_CHALLENGER = "challenger"
LIFECYCLE_CHAMPION = "champion"
LIFECYCLE_PRODUCTION_CANDIDATE = "production_candidate"
LIFECYCLE_ROLLED_BACK = "rolled_back"
LIFECYCLE_RETIRED = "retired"
LIFECYCLE_STATUSES = (
    LIFECYCLE_EXPERIMENTAL, LIFECYCLE_CHALLENGER, LIFECYCLE_CHAMPION,
    LIFECYCLE_PRODUCTION_CANDIDATE, LIFECYCLE_ROLLED_BACK, LIFECYCLE_RETIRED,
)


def _require_reviewer(reviewer: str) -> None:
    if not reviewer or not reviewer.strip():
        raise ValueError(
            "a promotion/rollback/quarantine action requires a non-empty human reviewer identity "
            "-- \"PROMPT 10\" §64 forbids automatic production promotion"
        )


def _audit(db: Session, *, actor: str, action: str, version: StrategyVersion, detail: dict) -> None:
    db.add(AuditLog(actor=actor, action=action, entity_type="strategy_version", entity_id=version.id, detail=detail))


def _next_version_label(db: Session, strategy_id: int) -> str:
    count = len(db.execute(select(StrategyVersion.id).where(StrategyVersion.strategy_id == strategy_id)).scalars().all())
    return f"v{count + 1}"


def create_version(
    db: Session, *, strategy_id: int, params: dict, changes: list[str] | None = None,
    dsl_definition: dict | None = None, validation_status: str = "EXPERIMENTAL",
    lifecycle_status: str = LIFECYCLE_EXPERIMENTAL, created_by: str = "autonomous_research_agent",
    parent_version_id: int | None = None, performance: dict | None = None,
) -> StrategyVersion:
    if validation_status not in STATUS_LABELS:
        raise ValueError(f"unknown validation_status: {validation_status!r} (expected one of {STATUS_LABELS})")
    if lifecycle_status not in LIFECYCLE_STATUSES:
        raise ValueError(f"unknown lifecycle_status: {lifecycle_status!r} (expected one of {LIFECYCLE_STATUSES})")
    if db.get(StrategyRow, strategy_id) is None:
        raise ValueError(f"unknown strategy_id: {strategy_id!r}")

    version = StrategyVersion(
        strategy_id=strategy_id, version=_next_version_label(db, strategy_id), parent_version_id=parent_version_id,
        changes=list(changes or []), dsl_definition=dsl_definition, params=params, performance=performance or {},
        validation_status=validation_status, lifecycle_status=lifecycle_status, created_by=created_by,
    )
    db.add(version)
    db.flush()
    _audit(
        db, actor=created_by, action="create_strategy_version", version=version,
        detail={"strategy_id": strategy_id, "version": version.version, "parent_version_id": parent_version_id},
    )
    db.commit()
    return version


def get_champion(db: Session, strategy_id: int) -> StrategyVersion | None:
    return (
        db.execute(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == strategy_id, StrategyVersion.lifecycle_status == LIFECYCLE_CHAMPION)
            .order_by(StrategyVersion.created_at.desc())
        )
        .scalars()
        .first()
    )


def get_challengers(db: Session, strategy_id: int) -> list[StrategyVersion]:
    return list(
        db.execute(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == strategy_id, StrategyVersion.lifecycle_status == LIFECYCLE_CHALLENGER)
            .order_by(StrategyVersion.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_lineage(db: Session, version_id: int) -> list[StrategyVersion]:
    """Walks `parent_version_id` back to the root — oldest first."""
    lineage: list[StrategyVersion] = []
    current = db.get(StrategyVersion, version_id)
    seen: set[int] = set()
    while current is not None and current.id not in seen:
        lineage.append(current)
        seen.add(current.id)
        current = db.get(StrategyVersion, current.parent_version_id) if current.parent_version_id else None
    return list(reversed(lineage))


def promote_to_challenger(db: Session, version_id: int, *, reviewer: str) -> StrategyVersion:
    _require_reviewer(reviewer)
    version = db.get(StrategyVersion, version_id)
    if version is None:
        raise ValueError(f"unknown strategy_version id: {version_id!r}")
    if version.lifecycle_status != LIFECYCLE_EXPERIMENTAL:
        raise ValueError(f"can only promote an 'experimental' version to challenger, got {version.lifecycle_status!r}")
    version.lifecycle_status = LIFECYCLE_CHALLENGER
    _audit(db, actor=reviewer, action="promote_to_challenger", version=version, detail={"from": LIFECYCLE_EXPERIMENTAL})
    db.commit()
    return version


def promote_to_champion(db: Session, version_id: int, *, reviewer: str) -> StrategyVersion:
    """Promotes a challenger to champion, retiring the strategy's prior
    champion (if any) -- at most one champion per strategy at a time."""
    _require_reviewer(reviewer)
    version = db.get(StrategyVersion, version_id)
    if version is None:
        raise ValueError(f"unknown strategy_version id: {version_id!r}")
    if version.lifecycle_status != LIFECYCLE_CHALLENGER:
        raise ValueError(f"can only promote a 'challenger' version to champion, got {version.lifecycle_status!r}")

    previous_champion = get_champion(db, version.strategy_id)
    if previous_champion is not None:
        previous_champion.lifecycle_status = LIFECYCLE_RETIRED
        _audit(
            db, actor=reviewer, action="retire_superseded_champion", version=previous_champion,
            detail={"superseded_by_version_id": version.id},
        )

    version.lifecycle_status = LIFECYCLE_CHAMPION
    _audit(
        db, actor=reviewer, action="promote_to_champion", version=version,
        detail={"from": LIFECYCLE_CHALLENGER, "previous_champion_version_id": previous_champion.id if previous_champion else None},
    )
    db.commit()
    return version


def rollback(db: Session, strategy_id: int, *, reviewer: str, to_version_id: int | None = None) -> StrategyVersion:
    """Rolls the current champion back, restoring `to_version_id` (or, if
    omitted, the most recently superseded champion found via the AuditLog
    trail `promote_to_champion` leaves behind) as the new champion. Reuses
    AuditLog as the append-only champion-history ledger rather than adding
    a dedicated history table.
    """
    _require_reviewer(reviewer)
    current_champion = get_champion(db, strategy_id)
    if current_champion is None:
        raise ValueError(f"strategy_id {strategy_id!r} has no current champion to roll back")

    if to_version_id is None:
        prior_promotion = (
            db.execute(
                select(AuditLog)
                .where(AuditLog.action == "promote_to_champion", AuditLog.entity_type == "strategy_version", AuditLog.entity_id != current_champion.id)
                .order_by(AuditLog.ts.desc())
            )
            .scalars()
            .first()
        )
        if prior_promotion is None or prior_promotion.entity_id is None:
            raise ValueError(f"no prior champion found for strategy_id {strategy_id!r} -- pass to_version_id explicitly")
        to_version_id = prior_promotion.entity_id

    restored = db.get(StrategyVersion, to_version_id)
    if restored is None or restored.strategy_id != strategy_id:
        raise ValueError(f"to_version_id {to_version_id!r} is not a version of strategy_id {strategy_id!r}")

    current_champion.lifecycle_status = LIFECYCLE_ROLLED_BACK
    _audit(db, actor=reviewer, action="rollback_champion", version=current_champion, detail={"restored_version_id": restored.id})

    restored.lifecycle_status = LIFECYCLE_CHAMPION
    _audit(db, actor=reviewer, action="restore_as_champion", version=restored, detail={"rolled_back_version_id": current_champion.id})

    db.commit()
    return restored


def retire(db: Session, version_id: int, *, reviewer: str, reason: str | None = None) -> StrategyVersion:
    _require_reviewer(reviewer)
    version = db.get(StrategyVersion, version_id)
    if version is None:
        raise ValueError(f"unknown strategy_version id: {version_id!r}")
    version.lifecycle_status = LIFECYCLE_RETIRED
    _audit(db, actor=reviewer, action="retire_version", version=version, detail={"reason": reason})
    db.commit()
    return version


def quarantine_version(db: Session, version_id: int, *, reviewer: str, reason: str) -> StrategyVersion:
    """Sets `validation_status="QUARANTINED"` -- lifecycle_status has no
    quarantine value of its own, so a champion/challenger being quarantined
    is also force-retired: a quarantined version can never keep serving as
    the strategy's live comparison point."""
    _require_reviewer(reviewer)
    version = db.get(StrategyVersion, version_id)
    if version is None:
        raise ValueError(f"unknown strategy_version id: {version_id!r}")
    version.validation_status = "QUARANTINED"
    if version.lifecycle_status in (LIFECYCLE_CHAMPION, LIFECYCLE_CHALLENGER):
        version.lifecycle_status = LIFECYCLE_RETIRED
    _audit(db, actor=reviewer, action="quarantine_version", version=version, detail={"reason": reason})
    db.commit()
    return version


def update_performance(db: Session, version_id: int, *, performance: dict, validation_status: str) -> StrategyVersion:
    if validation_status not in STATUS_LABELS:
        raise ValueError(f"unknown validation_status: {validation_status!r} (expected one of {STATUS_LABELS})")
    version = db.get(StrategyVersion, version_id)
    if version is None:
        raise ValueError(f"unknown strategy_version id: {version_id!r}")
    version.performance = performance
    version.validation_status = validation_status
    db.commit()
    return version


def run_shadow_evaluation(
    db: Session, *, champion: StrategyVersion, challenger: StrategyVersion, strategy_code: str, asset: Asset,
    timeframe: str, start_ts: datetime, end_ts: datetime, initial_capital: float,
    risk_limits: RiskLimits | None = None,
) -> ExperimentRow:
    """§31 Shadow Mode, scoped to this paper-trading-only system: evaluates
    the challenger against the champion over the most recent real market
    data via the same `ExperimentEngine` this phase already built, and
    attaches the result to the challenger's `performance`/`validation_status`
    -- never to the champion, which stays whatever it already was.
    """
    experiment = run_experiment(
        db, hypothesis_id=None, type="strategy_test",
        control=ArmSpec(strategy_code=strategy_code, params=champion.params, label=f"champion:{champion.version}"),
        candidate=ArmSpec(strategy_code=strategy_code, params=challenger.params, label=f"challenger:{challenger.version}"),
        asset=asset, timeframe=timeframe, start_ts=start_ts, end_ts=end_ts,
        initial_capital=initial_capital, risk_limits=risk_limits,
    )
    result = experiment.result or {}
    candidate_report = result.get("candidate_report", {})
    update_performance(
        db, challenger.id,
        performance={**challenger.performance, "shadow_experiment_id": experiment.id, "shadow_result": candidate_report},
        validation_status=candidate_report.get("quality_status", challenger.validation_status),
    )
    return experiment


def compare_champion_challenger(champion: StrategyVersion, challenger: StrategyVersion) -> dict:
    champion_perf, challenger_perf = champion.performance or {}, challenger.performance or {}
    if not champion_perf or not challenger_perf:
        return {"comparable": False, "reason": "champion and/or challenger has no recorded performance yet"}
    return {
        "comparable": True,
        "champion": {"version": champion.version, "validation_status": champion.validation_status, "performance": champion_perf},
        "challenger": {"version": challenger.version, "validation_status": challenger.validation_status, "performance": challenger_perf},
    }
