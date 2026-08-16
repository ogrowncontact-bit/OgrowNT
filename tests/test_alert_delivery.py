from apps.worker.alerts import run_alert_delivery_cycle
from packages.notifications.channels.base import ChannelResult
from packages.notifications.dispatcher import NotificationDispatcher
from packages.shared.models import Alert


class _FakeChannel:
    def __init__(self, name: str, status: str):
        self.name = name
        self._status = status

    def is_configured(self) -> bool:
        return self._status != "not_configured"

    def send(self, alert: Alert) -> ChannelResult:
        return ChannelResult(channel=self.name, status=self._status)


def test_pending_alert_gets_delivered_at_set(db_session):
    db_session.add(Alert(severity="warning", category="risk", message="test"))
    db_session.commit()

    dispatcher = NotificationDispatcher(channels=(_FakeChannel("fake", "sent"),))
    summary = run_alert_delivery_cycle(db_session, dispatcher)

    assert summary == {"attempted": 1, "sent": 1}
    alert = db_session.query(Alert).filter(Alert.message == "test").first()
    assert alert.delivered_at is not None
    assert alert.meta["_delivery"][0]["status"] == "sent"


def test_already_delivered_alert_is_not_reprocessed(db_session):
    from datetime import datetime, timezone

    db_session.add(Alert(severity="info", category="learning", message="already done", delivered_at=datetime.now(timezone.utc)))
    db_session.commit()

    dispatcher = NotificationDispatcher(channels=(_FakeChannel("fake", "sent"),))
    summary = run_alert_delivery_cycle(db_session, dispatcher)

    assert summary == {"attempted": 0, "sent": 0}


def test_no_channels_configured_still_marks_delivered(db_session):
    db_session.add(Alert(severity="warning", category="risk", message="unreachable"))
    db_session.commit()

    dispatcher = NotificationDispatcher(channels=(_FakeChannel("fake", "not_configured"),))
    summary = run_alert_delivery_cycle(db_session, dispatcher)

    assert summary == {"attempted": 1, "sent": 0}
    alert = db_session.query(Alert).filter(Alert.message == "unreachable").first()
    assert alert.delivered_at is not None


def test_multiple_pending_alerts_all_processed(db_session):
    db_session.add(Alert(severity="info", category="learning", message="one"))
    db_session.add(Alert(severity="warning", category="risk", message="two"))
    db_session.commit()

    dispatcher = NotificationDispatcher(channels=(_FakeChannel("fake", "sent"),))
    summary = run_alert_delivery_cycle(db_session, dispatcher)

    assert summary == {"attempted": 2, "sent": 2}


def test_preserves_existing_meta_when_adding_delivery_info(db_session):
    db_session.add(Alert(severity="warning", category="risk", message="has meta", meta={"strategy_id": 42}))
    db_session.commit()

    dispatcher = NotificationDispatcher(channels=(_FakeChannel("fake", "sent"),))
    run_alert_delivery_cycle(db_session, dispatcher)

    alert = db_session.query(Alert).filter(Alert.message == "has meta").first()
    assert alert.meta["strategy_id"] == 42
    assert "_delivery" in alert.meta
