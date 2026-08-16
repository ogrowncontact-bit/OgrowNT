"""NotificationDispatcher — fans one Alert out to every configured channel.

Never raises: a channel that isn't configured or fails to send is recorded
in the result, not thrown — one bad channel must never stop the others or
break the worker cycle that's delivering alerts (apps/worker/alerts.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.notifications.channels.base import ChannelResult, NotificationChannel
from packages.notifications.channels.email import EmailChannel
from packages.notifications.channels.telegram import TelegramChannel
from packages.notifications.channels.whatsapp import WhatsAppChannel
from packages.shared.models import Alert

DEFAULT_CHANNELS: tuple[NotificationChannel, ...] = (EmailChannel(), TelegramChannel(), WhatsAppChannel())


@dataclass(frozen=True)
class DispatchResult:
    results: list[ChannelResult] = field(default_factory=list)

    @property
    def any_sent(self) -> bool:
        return any(r.status == "sent" for r in self.results)

    @property
    def configured_channel_count(self) -> int:
        return sum(1 for r in self.results if r.status != "not_configured")


class NotificationDispatcher:
    def __init__(self, channels: tuple[NotificationChannel, ...] | None = None):
        self._channels = channels if channels is not None else DEFAULT_CHANNELS

    def dispatch(self, alert: Alert) -> DispatchResult:
        results = [channel.send(alert) for channel in self._channels]
        return DispatchResult(results=results)
