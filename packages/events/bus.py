"""CentralEventBus — "PROMPT 14" §71-73.

A single in-process, asyncio pub/sub primitive living inside the `apps/api`
process (the only process a browser talks to). §71's "todos os módulos podem
publicar eventos" is satisfied at the SOURCE level, not by every module in
this 13-phase codebase holding a bus handle: apps/worker (a separate OS
process) already writes every state-changing moment into `trading_events`/
`alerts` (packages/shared/models.py's TradingEvent/Alert — the established,
single, already-existing event/notification log this whole system funnels
into). packages/events/tailer.py bridges that DB log into THIS bus on a
short, fixed cadence inside apps/api itself — see that module's own
docstring for why a DB tail was chosen over Postgres LISTEN/NOTIFY or a
message broker, and docs/command-center.md for the full write-up.

This module is deliberately transport-agnostic: it knows nothing about
WebSockets. apps/api/websocket.py is the only caller that turns a
subscription into bytes over a socket.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from packages.events.channels import CHANNELS

# Bounded so a slow/disconnected subscriber can never grow memory without
# limit — a full queue drops the OLDEST event (the subscriber is already
# behind; losing a stale event is better than blocking every other
# subscriber on one slow reader). §102's "never fake real-time" is honored
# by the drop being visible: apps/api/websocket.py counts drops and the
# frontend surfaces them as a stale-data warning, never silently.
_QUEUE_MAXSIZE = 200


@dataclass(frozen=True)
class Event:
    """§72's event schema, verbatim: event_id, event_type, source, timestamp,
    payload, severity, correlation_id."""

    event_type: str
    source: str
    channel: str
    payload: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    correlation_id: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "severity": self.severity,
            "correlation_id": self.correlation_id,
        }


class CentralEventBus:
    """One instance per apps/api process (apps/api/main.py's lifespan owns
    it). subscribe()/publish() are the entire surface — no channel needs
    pre-registration, but publish() rejects an unrecognized channel name so
    a typo in a future caller fails loudly instead of silently vanishing."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = {c: set() for c in CHANNELS}
        self._dropped_count = 0

    @property
    def dropped_count(self) -> int:
        """Total events dropped across all channels because a subscriber's
        queue was full — surfaced by apps/api/websocket.py so a client that
        was falling behind can be told honestly, not left guessing."""
        return self._dropped_count

    def subscribe(self, channel: str) -> asyncio.Queue[Event]:
        if channel not in self._subscribers:
            raise ValueError(f"unknown channel: {channel!r} (valid: {CHANNELS})")
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers[channel].add(queue)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.get(channel, set()).discard(queue)

    def publish(self, event: Event) -> None:
        if event.channel not in self._subscribers:
            raise ValueError(f"unknown channel: {event.channel!r} (valid: {CHANNELS})")
        for queue in self._subscribers[event.channel]:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop-oldest: pull one item off (the subscriber's own
                # backlog) to make room, rather than dropping the NEW event
                # and leaving a subscriber stuck replaying stale history.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:  # pragma: no cover - race, harmless
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:  # pragma: no cover - defensive
                    pass
                self._dropped_count += 1

    def subscriber_count(self, channel: str) -> int:
        return len(self._subscribers.get(channel, set()))

    def total_subscribers(self) -> int:
        return sum(len(queues) for queues in self._subscribers.values())
