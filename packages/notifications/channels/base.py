"""NotificationChannel interface — docs/blueprint/12-roadmap.md Phase 7's
"canais de alerta adicionais". Every channel (email, Telegram, the WhatsApp
stub) implements this so packages/notifications/dispatcher.py never needs
to know which concrete channel it's talking to — the same pluggable-adapter
shape as packages/data/connectors/market/base.py and
packages/execution/adapters/base.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from packages.shared.models import Alert


@dataclass(frozen=True)
class ChannelResult:
    channel: str
    status: str  # "sent" | "failed" | "not_configured"
    detail: str | None = None


class NotificationChannel(Protocol):
    name: str

    def is_configured(self) -> bool:
        """True iff this channel has everything it needs (credentials,
        destination) to attempt a real send. False is a valid, honest
        state — not every deployment configures every channel."""
        ...

    def send(self, alert: Alert) -> ChannelResult:
        """Attempt delivery. Must never raise — network/API failures come
        back as a ChannelResult(status="failed", detail=...) so one bad
        channel can't break delivery to the others or crash the worker
        cycle calling it."""
        ...
