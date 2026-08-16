from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from packages.notifications.channels.email import EmailChannel
from packages.notifications.channels.telegram import TelegramChannel
from packages.notifications.channels.whatsapp import WhatsAppChannel
from packages.shared.models import Alert


def _alert(**overrides) -> Alert:
    defaults = dict(id=1, ts=datetime.now(timezone.utc), severity="warning", category="risk", message="test alert", meta={})
    defaults.update(overrides)
    return Alert(**defaults)


# --- Email -------------------------------------------------------------


def test_email_not_configured_without_host():
    channel = EmailChannel(host="", sender="", to="")
    assert channel.is_configured() is False
    result = channel.send(_alert())
    assert result.status == "not_configured"


def test_email_sends_successfully(monkeypatch):
    channel = EmailChannel(host="smtp.example.com", port=587, username="", password="", sender="bot@example.com", to="admin@example.com")
    assert channel.is_configured() is True

    mock_server = MagicMock()
    mock_smtp_cm = MagicMock()
    mock_smtp_cm.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_cm.__exit__ = MagicMock(return_value=False)

    with patch("packages.notifications.channels.email.smtplib.SMTP", return_value=mock_smtp_cm) as mock_smtp:
        result = channel.send(_alert())

    assert result.status == "sent"
    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=10)
    mock_server.sendmail.assert_called_once()


def test_email_send_failure_is_reported_not_raised(monkeypatch):
    channel = EmailChannel(host="smtp.example.com", port=587, username="", password="", sender="bot@example.com", to="admin@example.com")

    with patch("packages.notifications.channels.email.smtplib.SMTP", side_effect=OSError("connection refused")):
        result = channel.send(_alert())

    assert result.status == "failed"
    assert "connection refused" in result.detail


# --- Telegram ------------------------------------------------------------


def test_telegram_not_configured_without_token():
    channel = TelegramChannel(bot_token="", chat_id="")
    assert channel.is_configured() is False
    result = channel.send(_alert())
    assert result.status == "not_configured"


def test_telegram_sends_successfully():
    channel = TelegramChannel(bot_token="123:abc", chat_id="456")
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {"ok": True}

    with patch("packages.notifications.channels.telegram.httpx.post", return_value=mock_response) as mock_post:
        result = channel.send(_alert())

    assert result.status == "sent"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "123:abc" in call_kwargs.args[0]


def test_telegram_http_error_is_reported_not_raised():
    channel = TelegramChannel(bot_token="123:abc", chat_id="456")
    mock_response = MagicMock(status_code=401, text="Unauthorized")

    with patch("packages.notifications.channels.telegram.httpx.post", return_value=mock_response):
        result = channel.send(_alert())

    assert result.status == "failed"
    assert "401" in result.detail


def test_telegram_network_exception_is_reported_not_raised():
    channel = TelegramChannel(bot_token="123:abc", chat_id="456")

    with patch("packages.notifications.channels.telegram.httpx.post", side_effect=ConnectionError("dns failure")):
        result = channel.send(_alert())

    assert result.status == "failed"
    assert "dns failure" in result.detail


# --- WhatsApp (explicit stub) --------------------------------------------


def test_whatsapp_is_never_configured():
    channel = WhatsAppChannel()
    assert channel.is_configured() is False
    result = channel.send(_alert())
    assert result.status == "not_configured"
