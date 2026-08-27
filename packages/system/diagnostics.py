"""Self Diagnostic — "PROMPT 14" §124-129.

A small set of REAL, lightweight probes against subsystems this process can
actually reach without side effects — never a claim about a subsystem the
check can't genuinely test (packages/data/quality.py's "no hallucinated
data" discipline applies here too). apps/api/main.py's lifespan runs this
once at startup (best-effort, non-blocking — a NOT_READY result doesn't
crash the process, it's surfaced honestly via GET /api/system/diagnostics
instead, same "fail loud, not fail silent" convention as every health check
in this codebase); it's also callable on demand from that same endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from packages.events.bus import CentralEventBus
from packages.shared.models import OHLCV, Broker, SystemState
from packages.shared.settings import get_settings
from packages.shared.worker_health import is_heartbeat_stale


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class SelfDiagnosticReport:
    ok: bool
    checks: list[DiagnosticCheck] = field(default_factory=list)
    ran_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def run_self_diagnostic(db: Session, *, bus: CentralEventBus | None = None) -> SelfDiagnosticReport:
    checks: list[DiagnosticCheck] = []

    try:
        db.execute(text("SELECT 1"))
        checks.append(DiagnosticCheck("database", True, "reachable"))
    except Exception as exc:  # noqa: BLE001 - report, never crash the caller
        checks.append(DiagnosticCheck("database", False, str(exc)))

    # Each remaining check gets its own try/except -- a connection that died
    # between the "database" check above and here (or that dies mid-check)
    # must not take down every check after it; the whole point of this
    # report is to stay honest and complete precisely when something is
    # already broken, not to raise instead of describing the breakage.
    try:
        latest = db.execute(select(OHLCV).order_by(OHLCV.ts.desc()).limit(1)).scalar_one_or_none()
        if latest is None:
            checks.append(DiagnosticCheck("data", False, "no OHLCV rows exist yet"))
        else:
            age_seconds = (datetime.now(timezone.utc) - latest.ts).total_seconds()
            fresh = age_seconds < max(3 * get_settings().scan_interval_seconds, 180)
            checks.append(DiagnosticCheck("data", fresh, f"latest candle {age_seconds:.0f}s old"))
    except Exception as exc:  # noqa: BLE001 - report, never crash the caller
        checks.append(DiagnosticCheck("data", False, str(exc)))

    try:
        state = db.get(SystemState, True)
        worker_alive = state is not None and not is_heartbeat_stale(
            state.worker_last_heartbeat, scan_interval_seconds=get_settings().scan_interval_seconds
        )
        checks.append(
            DiagnosticCheck("workers", worker_alive, "worker heartbeat fresh" if worker_alive else "worker heartbeat stale or missing")
        )
    except Exception as exc:  # noqa: BLE001 - report, never crash the caller
        checks.append(DiagnosticCheck("workers", False, str(exc)))

    try:
        broker = db.query(Broker).filter(Broker.status == "active").first()
        checks.append(
            DiagnosticCheck("broker", broker is not None, "an active broker is registered" if broker is not None else "no active broker registered")
        )
    except Exception as exc:  # noqa: BLE001 - report, never crash the caller
        checks.append(DiagnosticCheck("broker", False, str(exc)))

    if bus is not None:
        checks.append(DiagnosticCheck("event_bus", True, f"{bus.total_subscribers()} live subscriber(s)"))
    else:
        checks.append(DiagnosticCheck("event_bus", False, "bus not available to this check"))

    return SelfDiagnosticReport(ok=all(c.ok for c in checks), checks=checks)
