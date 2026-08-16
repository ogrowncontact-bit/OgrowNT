"""Email delivery via stdlib smtplib — no third-party email SDK needed for
a single outgoing SMTP connection. Configured via SMTP_* + ALERT_EMAIL_TO
(packages/shared/settings.py); any missing piece means `is_configured()` is
False and this channel is honestly skipped, never a fabricated "sent".
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from packages.notifications.channels.base import ChannelResult
from packages.shared.models import Alert
from packages.shared.settings import get_settings

logger = logging.getLogger("notifications.email")


class EmailChannel:
    name = "email"

    def __init__(
        self, *, host: str | None = None, port: int | None = None, username: str | None = None,
        password: str | None = None, sender: str | None = None, to: str | None = None,
    ) -> None:
        s = get_settings()
        self._host = host if host is not None else s.smtp_host
        self._port = port if port is not None else s.smtp_port
        self._username = username if username is not None else s.smtp_username
        self._password = password if password is not None else s.smtp_password
        self._from = sender if sender is not None else s.smtp_from
        self._to = to if to is not None else s.alert_email_to

    def is_configured(self) -> bool:
        return bool(self._host and self._from and self._to)

    def send(self, alert: Alert) -> ChannelResult:
        if not self.is_configured():
            return ChannelResult(channel=self.name, status="not_configured")

        subject = f"[OgrowNT] {alert.severity.upper()} — {alert.category}"
        body = f"{alert.message}\n\ntime: {alert.ts.isoformat()}\nmeta: {alert.meta}"
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = self._to

        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as server:
                server.starttls()
                if self._username:
                    server.login(self._username, self._password)
                server.sendmail(self._from, [self._to], msg.as_string())
            return ChannelResult(channel=self.name, status="sent")
        except Exception as exc:  # noqa: BLE001 - a bad channel must never break delivery to others
            logger.exception("Email alert delivery failed")
            return ChannelResult(channel=self.name, status="failed", detail=str(exc))
