"""Worker supervisor — Prompt 10's "Supervisor 24/7", scoped narrowly to
what apps/worker/main.py's single loop was actually missing: honest
liveness (docs/blueprint/00-overview.md's "no hallucinated data" applies to
the worker's own health, not just market data) and a signal when a cadence
has been failing repeatedly, rather than only a log line no one reads until
something has clearly gone wrong.

Deliberately not a "Master Agent" dispatch framework — that was considered
and rejected (docs/blueprint/01-repo-structure.md's "O que não existe e
porquê"): apps/worker/main.py stays one loop, one cadence per
responsibility. This module only adds the per-cadence failure counter the
loop already needed; the heartbeat read/write lives in
packages/shared/worker_health.py since apps/api's health endpoint reads it
too (apps/api never imports from apps/worker).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from packages.shared.models import Alert

# A single transient failure (a momentary DB blip, a flaky mock-provider
# hiccup) is normal and already logged — only a *sustained* one needs to
# interrupt the operator via the Phase 7 alert-delivery pipeline.
CONSECUTIVE_FAILURE_ALERT_THRESHOLD = 3


class CadenceFailureTracker:
    """One instance per worker process. Tracks consecutive failures per
    cadence name (in-memory — resets on restart, which is fine: a fresh
    process deserves a fresh count, not a stale complaint from before it
    started)."""

    def __init__(self) -> None:
        self._consecutive_failures: dict[str, int] = {}

    def record_success(self, cadence: str) -> None:
        self._consecutive_failures[cadence] = 0

    def record_failure(self, db: Session, cadence: str, error: str) -> int:
        """Returns the new consecutive-failure count. Raises an Alert
        exactly once per threshold crossing (at CONSECUTIVE_FAILURE_ALERT_THRESHOLD),
        not on every failure after — a sustained outage should page the
        operator once, not flood their inbox on every subsequent tick."""
        count = self._consecutive_failures.get(cadence, 0) + 1
        self._consecutive_failures[cadence] = count
        if count == CONSECUTIVE_FAILURE_ALERT_THRESHOLD:
            db.add(
                Alert(
                    severity="warning", category="system",
                    message=f"Worker cadence '{cadence}' has failed {count} times in a row: {error}",
                    meta={"cadence": cadence, "consecutive_failures": count, "last_error": error},
                )
            )
            db.commit()
        return count
