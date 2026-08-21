"""BrokerEvent store — "PROMPT 13" §102-103.

An idempotent event log: the same (broker_id, event_type, payload) received
twice is a no-op — record_event() returns the EXISTING row rather than
inserting a duplicate (§103's "processar somente uma vez"), and the
(broker_id, event_type, payload_hash) unique constraint on the table itself
(packages/shared/models.py) makes this true even under a genuine race, not
just by convention.

record_event() is called from apps/worker/broker_health.py on every health
check — a naturally periodic, already-real event to log (§102) rather than
fabricating a synthetic one just to exercise this table.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.shared.models import BrokerEvent


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def record_event(
    db: Session, *, broker_id: int, event_type: str, payload: dict, sequence: int | None = None,
) -> tuple[BrokerEvent, bool]:
    """Returns (event, created). created=False means an identical event was
    already recorded (idempotent dedup) — the EXISTING row is returned
    unchanged, never a duplicate insert."""
    payload_hash = _hash_payload(payload)
    existing = (
        db.query(BrokerEvent)
        .filter(BrokerEvent.broker_id == broker_id, BrokerEvent.event_type == event_type, BrokerEvent.payload_hash == payload_hash)
        .one_or_none()
    )
    if existing is not None:
        return existing, False

    event = BrokerEvent(
        broker_id=broker_id, event_type=event_type, payload_hash=payload_hash, sequence=sequence,
        processed=True, detail=payload, ts=datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()
    return event, True
