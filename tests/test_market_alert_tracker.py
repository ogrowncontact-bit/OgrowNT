from apps.worker.market_alerts import MarketAlertTracker
from packages.shared.models import Alert


def test_first_alert_for_a_key_fires(db_session):
    tracker = MarketAlertTracker(cooldown_seconds=900)
    fired = tracker.maybe_alert(db_session, key="feed:mock", severity="critical", message="down")
    assert fired is True
    assert db_session.query(Alert).filter(Alert.category == "market").count() == 1


def test_repeated_alert_within_cooldown_is_suppressed(db_session):
    tracker = MarketAlertTracker(cooldown_seconds=900)
    tracker.maybe_alert(db_session, key="feed:mock", severity="critical", message="down")
    fired_again = tracker.maybe_alert(db_session, key="feed:mock", severity="critical", message="still down")
    assert fired_again is False
    assert db_session.query(Alert).filter(Alert.category == "market").count() == 1


def test_alert_fires_again_after_cooldown_expires(db_session, monkeypatch):
    tracker = MarketAlertTracker(cooldown_seconds=1)
    tracker.maybe_alert(db_session, key="feed:mock", severity="critical", message="down")

    import time as time_module

    real_time = time_module.monotonic()
    monkeypatch.setattr(time_module, "monotonic", lambda: real_time + 10)

    fired_again = tracker.maybe_alert(db_session, key="feed:mock", severity="critical", message="still down")
    assert fired_again is True
    assert db_session.query(Alert).filter(Alert.category == "market").count() == 2


def test_clear_lets_the_next_alert_fire_immediately(db_session):
    tracker = MarketAlertTracker(cooldown_seconds=900)
    tracker.maybe_alert(db_session, key="feed:mock", severity="critical", message="down")
    tracker.clear("feed:mock")

    fired_again = tracker.maybe_alert(db_session, key="feed:mock", severity="critical", message="down again")
    assert fired_again is True
    assert db_session.query(Alert).filter(Alert.category == "market").count() == 2


def test_independent_keys_do_not_interfere(db_session):
    tracker = MarketAlertTracker(cooldown_seconds=900)
    tracker.maybe_alert(db_session, key="feed:mock", severity="critical", message="down")
    fired_other = tracker.maybe_alert(db_session, key="event:BTCUSDT:VOLUME_SPIKE", severity="warning", message="spike")
    assert fired_other is True
    assert db_session.query(Alert).filter(Alert.category == "market").count() == 2
