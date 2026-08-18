"""Worker liveness — read by apps/api (health endpoint) and written by
apps/worker (once per loop iteration). Lives here rather than in
apps/worker, matching packages/shared/market_data.py's precedent: a small
read/write helper both apps/api and apps/worker need, so apps/api never has
to import from apps/worker (see docs/blueprint/01-repo-structure.md's
package dependency rules).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.shared.models import SystemState

# How stale a heartbeat has to be before /api/system/health reports the
# worker as down. A generous multiple of one scan cycle so a single slow
# iteration doesn't flap the status, with a floor for very short intervals.
HEARTBEAT_STALE_MULTIPLIER = 3
HEARTBEAT_STALE_FLOOR_SECONDS = 180


def record_heartbeat(db: Session) -> None:
    """Called once per full worker loop iteration, regardless of whether
    any cadence inside it succeeded — this proves the loop itself is alive,
    not that everything it did succeeded."""
    state = db.get(SystemState, True)
    if state is None:
        state = SystemState(id=True)
    state.worker_last_heartbeat = datetime.now(timezone.utc)
    db.add(state)
    db.commit()


def is_heartbeat_stale(last_heartbeat: datetime | None, *, scan_interval_seconds: int, now: datetime | None = None) -> bool:
    if last_heartbeat is None:
        return True
    now = now or datetime.now(timezone.utc)
    stale_after = max(HEARTBEAT_STALE_MULTIPLIER * scan_interval_seconds, HEARTBEAT_STALE_FLOOR_SECONDS)
    return (now - last_heartbeat).total_seconds() > stale_after
