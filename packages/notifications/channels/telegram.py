"""Telegram delivery via the Bot API's sendMessage endpoint — one HTTPS
POST, no SDK needed. Configured via TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
(packages/shared/settings.py); missing either means `is_configured()` is
False, the same honest-degradation convention used everywhere else in this
codebase (e.g. packages/llm/client.py's ANTHROPIC_API_KEY).
"""
from __future__ import annotations

import logging

import httpx

from packages.notifications.channels.base import ChannelResult
from packages.shared.models import Alert
from packages.shared.settings import get_settings

logger = logging.getLogger("notifications.telegram")

_API_BASE = "https://api.telegram.org"
_TIMEOUT_SECONDS = 10.0


class TelegramChannel:
    name = "telegram"

    def __init__(self, *, bot_token: str | None = None, chat_id: str | None = None) -> None:
        s = get_settings()
        self._bot_token = bot_token if bot_token is not None else s.telegram_bot_token
        self._chat_id = chat_id if chat_id is not None else s.telegram_chat_id

    def is_configured(self) -> bool:
        return bool(self._bot_token and self._chat_id)

    def send(self, alert: Alert) -> ChannelResult:
        if not self.is_configured():
            return ChannelResult(channel=self.name, status="not_configured")

        text = f"[{alert.severity.upper()}/{alert.category}] {alert.message}"
        url = f"{_API_BASE}/bot{self._bot_token}/sendMessage"

        try:
            response = httpx.post(url, json={"chat_id": self._chat_id, "text": text}, timeout=_TIMEOUT_SECONDS)
            if response.status_code == 200 and response.json().get("ok"):
                return ChannelResult(channel=self.name, status="sent")
            return ChannelResult(channel=self.name, status="failed", detail=f"HTTP {response.status_code}: {response.text[:200]}")
        except Exception as exc:  # noqa: BLE001 - a bad channel must never break delivery to others
            logger.exception("Telegram alert delivery failed")
            return ChannelResult(channel=self.name, status="failed", detail=str(exc))
