"""WhatsApp — explicitly NOT implemented, not a fake/mock channel.

Unlike email (stdlib smtplib) and Telegram (one unauthenticated-beyond-a-
bot-token HTTPS POST), a real WhatsApp send requires either a paid Twilio
account or Meta's WhatsApp Business Cloud API (OAuth app review, a
verified business phone number) — infrastructure this project has no
account for and cannot provision from inside a coding session. Rather than
fabricate a channel that silently no-ops and claims to be "configured", or
skip it from the roadmap item without a trace, this class exists so the
interface (packages/notifications/channels/base.py) stays complete and
pluggable — `is_configured()` is unconditionally False, so
packages/notifications/dispatcher.py always treats it as an honestly
unavailable channel, exactly like every other "not configured" state in
this codebase.

TODO(real-whatsapp): once a real Business API account + credentials exist,
implement `send()` against that account's HTTP API here — the
NotificationChannel interface does not need to change.
"""
from __future__ import annotations

from packages.notifications.channels.base import ChannelResult
from packages.shared.models import Alert


class WhatsAppChannel:
    name = "whatsapp"

    def is_configured(self) -> bool:
        return False

    def send(self, alert: Alert) -> ChannelResult:
        return ChannelResult(channel=self.name, status="not_configured", detail="WhatsApp Business API integration not implemented")
