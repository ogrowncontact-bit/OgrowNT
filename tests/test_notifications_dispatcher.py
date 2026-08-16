from datetime import datetime, timezone

from packages.notifications.channels.base import ChannelResult
from packages.notifications.dispatcher import NotificationDispatcher
from packages.shared.models import Alert


class _FakeChannel:
    def __init__(self, name: str, status: str):
        self.name = name
        self._status = status
        self.calls = 0

    def is_configured(self) -> bool:
        return self._status != "not_configured"

    def send(self, alert: Alert) -> ChannelResult:
        self.calls += 1
        return ChannelResult(channel=self.name, status=self._status)


def _alert() -> Alert:
    return Alert(id=1, ts=datetime.now(timezone.utc), severity="warning", category="risk", message="x", meta={})


def test_dispatch_calls_every_channel():
    a, b = _FakeChannel("a", "sent"), _FakeChannel("b", "not_configured")
    dispatcher = NotificationDispatcher(channels=(a, b))
    result = dispatcher.dispatch(_alert())

    assert a.calls == 1 and b.calls == 1
    assert len(result.results) == 2


def test_any_sent_true_when_one_channel_succeeds():
    dispatcher = NotificationDispatcher(channels=(_FakeChannel("a", "failed"), _FakeChannel("b", "sent")))
    result = dispatcher.dispatch(_alert())
    assert result.any_sent is True


def test_any_sent_false_when_none_succeed():
    dispatcher = NotificationDispatcher(channels=(_FakeChannel("a", "failed"), _FakeChannel("b", "not_configured")))
    result = dispatcher.dispatch(_alert())
    assert result.any_sent is False


def test_configured_channel_count_excludes_not_configured():
    dispatcher = NotificationDispatcher(channels=(_FakeChannel("a", "sent"), _FakeChannel("b", "not_configured"), _FakeChannel("c", "failed")))
    result = dispatcher.dispatch(_alert())
    assert result.configured_channel_count == 2


def test_no_channels_configured_is_a_valid_empty_result():
    dispatcher = NotificationDispatcher(channels=(_FakeChannel("a", "not_configured"),))
    result = dispatcher.dispatch(_alert())
    assert result.any_sent is False
    assert result.configured_channel_count == 0
