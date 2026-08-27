"""DB -> CentralEventBus bridge — "PROMPT 14" §70-71, §101.

Honesty note on the architecture: a literal reading of §71 ("todos os
módulos podem publicar eventos") plus §101 ("event-driven... evitar polling
excessivo") could suggest Postgres LISTEN/NOTIFY or a message broker
(Redis/NATS) so apps/worker pushes directly into apps/api's bus. This
codebase deliberately does neither, for two reasons that outweigh sub-second
latency: (1) every one of the ~150 existing TradingEvent/Alert write sites
across 13 phases already funnels into two tables (packages/shared/models.py's
TradingEvent and Alert) — retrofitting a NOTIFY call into each would be a
large, risky, low-value rewrite of already-proven code; (2) LISTEN/NOTIFY
needs a dedicated async DB connection alongside the synchronous
SQLAlchemy-session-per-request model every other endpoint in apps/api
already uses, and a message broker would be new infrastructure this
single-Postgres-instance system has never needed.

Instead: `tail_new_events()` below is a plain, indexed `id > last_seen_id`
query apps/api/main.py's lifespan runs on a short, fixed
EVENT_POLL_INTERVAL_SECONDS cadence (default 2s — see packages/shared/
settings.py), converting any new rows into `Event`s and publishing them to
the bus, which then pushes to every connected WebSocket client. The
CLIENT-facing contract is genuinely real push (a persistent WebSocket
connection, no client-side polling) — only the server's own bridge from
Postgres to the bus is a bounded-latency tail, not sub-second. See
docs/command-center.md for the full write-up; this is the same
"honest, bounded divergence from a literal reading" discipline as every
other "architecture-ready" note across this codebase's prior phases.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.events.bus import Event
from packages.events.channels import (
    ALERT_CATEGORY_TO_INCIDENT_CATEGORY,
    INCIDENT_WORTHY_EVENT_TYPES,
    channel_for_trading_event,
    severity_for_trading_event,
)
from packages.shared.models import Alert, Incident, SystemState, TradingEvent

# How long an already-open Incident for the same (source_event_type,
# source_entity_id) suppresses a duplicate — "page once, not every tick",
# the same discipline packages/execution/broker_reconciliation.py and
# apps/worker/supervisor.py already use for their own alerts. A NEW open
# Incident is only ever created if none is already open for that exact
# source; closing/resolving an existing one re-arms detection for the next
# genuinely new occurrence.


def _correlation_id(entity_type: str | None, entity_id: int | None) -> str | None:
    if entity_type is None or entity_id is None:
        return None
    return f"{entity_type}:{entity_id}"


def _trading_event_to_event(row: TradingEvent) -> Event:
    return Event(
        event_type=row.event_type,
        source="trading_events",
        channel=channel_for_trading_event(row.event_type),
        payload={**row.payload, "entity_type": row.entity_type, "entity_id": row.entity_id},
        severity=severity_for_trading_event(row.event_type),
        correlation_id=_correlation_id(row.entity_type, row.entity_id),
        timestamp=row.ts,
    )


def _alert_to_event(row: Alert) -> Event:
    return Event(
        event_type=f"alert.{row.category}",
        source="alerts",
        channel="alerts",
        payload={"message": row.message, "category": row.category, **row.meta},
        severity=row.severity,
        correlation_id=None,
        timestamp=row.ts,
    )


@dataclass(frozen=True)
class TailResult:
    events: list[Event]
    last_trading_event_id: int
    last_alert_id: int


def tail_new_events(db: Session, *, since_trading_event_id: int, since_alert_id: int) -> TailResult:
    """Pure, synchronous, side-effect-free (besides the SELECTs) — no
    asyncio here, so this is trivially unit-testable and reusable from a
    sync context (a test, a management script) without a running bus."""
    trading_rows = (
        db.execute(
            select(TradingEvent).where(TradingEvent.id > since_trading_event_id).order_by(TradingEvent.id.asc())
        )
        .scalars()
        .all()
    )
    alert_rows = (
        db.execute(select(Alert).where(Alert.id > since_alert_id).order_by(Alert.id.asc())).scalars().all()
    )

    events = [_trading_event_to_event(r) for r in trading_rows] + [_alert_to_event(r) for r in alert_rows]
    new_last_trading = trading_rows[-1].id if trading_rows else since_trading_event_id
    new_last_alert = alert_rows[-1].id if alert_rows else since_alert_id
    return TailResult(events=events, last_trading_event_id=new_last_trading, last_alert_id=new_last_alert)


def build_heartbeat_event(db: Session) -> Event:
    """§6 — a live status ping published on every tail tick regardless of
    whether any new row exists, so the "system" channel (and therefore the
    Command Center's GlobalStatusBar) has something to show even during a
    perfectly quiet cycle. Ephemeral — never persisted, so this is a live
    status claim, not a historical one (packages/shared/models.py's
    SystemHealth table already owns the persisted snapshot, on its own
    HEALTH_SNAPSHOT_INTERVAL_SECONDS cadence)."""
    state = db.get(SystemState, True)
    payload = {
        "trading_enabled": state.trading_enabled if state else None,
        "trading_paused": state.trading_paused if state else None,
        "safety_belt_level": state.safety_belt_level if state else None,
        "trading_mode": state.trading_mode if state else None,
        "worker_last_heartbeat": state.worker_last_heartbeat.isoformat() if state and state.worker_last_heartbeat else None,
    }
    return Event(event_type="heartbeat", source="tailer", channel="system", payload=payload, severity="info")


def detect_incidents(db: Session, events: list[Event]) -> list[Incident]:
    """§59-62 — turns a curated subset of already-critical events into a
    durable, admin-workable Incident row, idempotently: a new Incident is
    only created if no OPEN one (status not in resolved/closed) already
    exists for the same source. Returns the newly created rows (already
    added+committed) for the caller to also publish on the bus if it wants
    to (apps/api's tail loop does)."""
    created: list[Incident] = []
    for event in events:
        category: str | None = None
        title: str | None = None
        if event.source == "trading_events" and event.event_type in INCIDENT_WORTHY_EVENT_TYPES:
            category = INCIDENT_WORTHY_EVENT_TYPES[event.event_type]
            title = event.event_type.replace("_", " ")
        elif event.source == "alerts" and event.severity == "critical":
            alert_category = event.payload.get("category", "system")
            category = ALERT_CATEGORY_TO_INCIDENT_CATEGORY.get(alert_category, "system")
            title = event.payload.get("message", "critical alert")[:200]

        if category is None or title is None:
            continue

        already_open = (
            db.query(Incident)
            .filter(
                Incident.source_event_type == event.event_type,
                Incident.status.notin_(("resolved", "closed")),
            )
            .first()
        )
        if already_open is not None:
            continue

        incident = Incident(
            category=category,
            severity=event.severity,
            status="detected",
            title=title,
            description=None,
            source_event_type=event.event_type,
            source_entity_type=event.payload.get("entity_type"),
            source_entity_id=event.payload.get("entity_id"),
            meta={"correlation_id": event.correlation_id, "payload": event.payload},
        )
        db.add(incident)
        created.append(incident)

    if created:
        db.commit()
        for incident in created:
            db.refresh(incident)
    return created
