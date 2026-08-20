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

from packages.shared.models import Position, SystemHealth, SystemState, TradingEvent

# How stale a heartbeat has to be before /api/system/health reports the
# worker as down. A generous multiple of one scan cycle so a single slow
# iteration doesn't flap the status, with a floor for very short intervals.
HEARTBEAT_STALE_MULTIPLIER = 3
HEARTBEAT_STALE_FLOOR_SECONDS = 180

# "PROMPT 8" §62's AutonomousSystemStatus enum, minus NO_TRADE and ERROR-
# from-an-unhandled-exception: NO_TRADE is a per-decision fact (surfaced by
# the 'no_trade' TradingEvent apps/worker/risk_execution.py already writes
# per signal), not a fact derivable from SystemState alone — asserting it
# here without per-cycle evidence would be exactly the kind of guess
# docs/blueprint/00-overview.md's "no hallucinated data" rule forbids.
AUTONOMOUS_STATUS_STARTING = "starting"
AUTONOMOUS_STATUS_RUNNING = "running"
AUTONOMOUS_STATUS_PAUSED = "paused"
AUTONOMOUS_STATUS_CAUTION = "caution"
AUTONOMOUS_STATUS_DEFENSIVE = "defensive"
AUTONOMOUS_STATUS_EMERGENCY = "emergency"
AUTONOMOUS_STATUS_KILL_SWITCH = "kill_switch"
AUTONOMOUS_STATUS_ERROR = "error"


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


def record_backtest_worker_heartbeat(db: Session) -> None:
    """Same idea as record_heartbeat(), for the separate apps/backtest_worker
    process ("PROMPT 7" §46-47) — a distinct SystemState column so this
    on-demand/batch process's liveness never gets conflated with the live
    trading worker's (see SystemState.backtest_worker_last_heartbeat)."""
    state = db.get(SystemState, True)
    if state is None:
        state = SystemState(id=True)
    state.backtest_worker_last_heartbeat = datetime.now(timezone.utc)
    db.add(state)
    db.commit()


def record_worker_restart(db: Session, *, max_restarts: int, window_seconds: int) -> bool:
    """Called once at apps/worker/main.py process startup — "PROMPT 8"
    §66's crash-loop protection. Docker's `restart: unless-stopped` already
    restarts a crashed process at the OS level; this only stops that from
    silently keeping trading "on" if the process is crash-looping (dies
    within seconds of every restart, never completing a real cycle).
    Returns True iff this call just triggered the pause (so the caller can
    log it loudly)."""
    state = db.get(SystemState, True)
    if state is None:
        state = SystemState(id=True)
        db.add(state)
        db.commit()

    now = datetime.now(timezone.utc)
    window_expired = (
        state.restart_window_started_at is None
        or (now - state.restart_window_started_at).total_seconds() > window_seconds
    )
    if window_expired:
        state.restart_window_started_at = now
        state.worker_restart_count = 1
    else:
        state.worker_restart_count += 1

    triggered = False
    if state.worker_restart_count > max_restarts and not state.trading_paused:
        state.trading_paused = True
        state.paused_reason = f"crash_loop_protection: {state.worker_restart_count} restarts within {window_seconds}s"
        state.paused_at = now
        triggered = True

    db.add(state)
    if triggered:
        db.add(
            TradingEvent(
                event_type="crash_loop_protection_triggered", entity_type="system_state", entity_id=None,
                payload={"restart_count": state.worker_restart_count, "window_seconds": window_seconds},
            )
        )
    else:
        db.add(
            TradingEvent(
                event_type="worker_restarted", entity_type="system_state", entity_id=None,
                payload={"restart_count": state.worker_restart_count},
            )
        )
    db.commit()
    return triggered


def compute_autonomous_status(state: SystemState, *, safety_belt_level: str, worker_alive: bool) -> str:
    """"PROMPT 8" §62's AutonomousSystemStatus — one honest priority order,
    most severe first, shared by the SystemHealth snapshot below and
    apps/api/routers/system.py's status endpoint so the two can never
    disagree about what the system is currently doing."""
    if state.worker_last_heartbeat is None:
        return AUTONOMOUS_STATUS_STARTING
    if not worker_alive:
        return AUTONOMOUS_STATUS_ERROR
    if not state.trading_enabled:
        return AUTONOMOUS_STATUS_KILL_SWITCH
    if safety_belt_level == "emergency":
        return AUTONOMOUS_STATUS_EMERGENCY
    if safety_belt_level == "defensive":
        return AUTONOMOUS_STATUS_DEFENSIVE
    if safety_belt_level == "caution":
        return AUTONOMOUS_STATUS_CAUTION
    if state.trading_paused:
        return AUTONOMOUS_STATUS_PAUSED
    return AUTONOMOUS_STATUS_RUNNING


def record_system_health_snapshot(db: Session, *, cadence_failures: dict | None = None) -> SystemHealth:
    """"PROMPT 8" §62-66's SystemHealthMonitor — a periodic, persisted
    snapshot; GET /api/system/health (apps/api/routers/system.py) computes
    the same kind of picture on demand but never stores it, so it can only
    ever answer "right now", not "an hour ago"."""
    state = db.get(SystemState, True)
    if state is None:
        state = SystemState(id=True)
        db.add(state)
        db.commit()

    from packages.shared.settings import get_settings

    worker_alive = not is_heartbeat_stale(state.worker_last_heartbeat, scan_interval_seconds=get_settings().scan_interval_seconds)
    autonomous_status = compute_autonomous_status(state, safety_belt_level=state.safety_belt_level, worker_alive=worker_alive)
    open_positions_count = db.query(Position).filter(Position.status == "open").count()

    snapshot = SystemHealth(
        ts=datetime.now(timezone.utc),
        autonomous_status=autonomous_status,
        trading_mode=state.trading_mode,
        trading_enabled=state.trading_enabled,
        trading_paused=state.trading_paused,
        safety_belt_level=state.safety_belt_level,
        worker_alive=worker_alive,
        open_positions_count=open_positions_count,
        cadence_failures=cadence_failures or {},
    )
    db.add(snapshot)
    db.commit()
    return snapshot
