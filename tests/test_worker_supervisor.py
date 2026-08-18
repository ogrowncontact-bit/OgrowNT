from apps.worker.supervisor import CONSECUTIVE_FAILURE_ALERT_THRESHOLD, CadenceFailureTracker
from packages.shared.models import Alert


def test_record_success_keeps_counter_at_zero(db_session):
    tracker = CadenceFailureTracker()
    tracker.record_success("scan_monitor")
    assert tracker._consecutive_failures["scan_monitor"] == 0


def test_record_failure_increments_counter(db_session):
    tracker = CadenceFailureTracker()
    count = tracker.record_failure(db_session, "news", "boom")
    assert count == 1
    count = tracker.record_failure(db_session, "news", "boom again")
    assert count == 2


def test_no_alert_before_threshold(db_session):
    tracker = CadenceFailureTracker()
    for _ in range(CONSECUTIVE_FAILURE_ALERT_THRESHOLD - 1):
        tracker.record_failure(db_session, "research", "still failing")

    alerts = db_session.query(Alert).filter(Alert.category == "system").all()
    assert alerts == []


def test_alert_raised_exactly_at_threshold(db_session):
    tracker = CadenceFailureTracker()
    for _ in range(CONSECUTIVE_FAILURE_ALERT_THRESHOLD):
        tracker.record_failure(db_session, "strategy", "db timeout")

    alerts = db_session.query(Alert).filter(Alert.category == "system").all()
    assert len(alerts) == 1
    assert alerts[0].severity == "warning"
    assert "strategy" in alerts[0].message
    assert alerts[0].meta["consecutive_failures"] == CONSECUTIVE_FAILURE_ALERT_THRESHOLD


def test_alert_not_repeated_past_threshold(db_session):
    tracker = CadenceFailureTracker()
    for _ in range(CONSECUTIVE_FAILURE_ALERT_THRESHOLD + 3):
        tracker.record_failure(db_session, "alert_delivery", "smtp down")

    alerts = db_session.query(Alert).filter(Alert.category == "system").all()
    assert len(alerts) == 1


def test_success_resets_and_a_new_failure_streak_alerts_again(db_session):
    tracker = CadenceFailureTracker()
    for _ in range(CONSECUTIVE_FAILURE_ALERT_THRESHOLD):
        tracker.record_failure(db_session, "news", "first outage")
    tracker.record_success("news")

    for _ in range(CONSECUTIVE_FAILURE_ALERT_THRESHOLD):
        tracker.record_failure(db_session, "news", "second outage")

    alerts = db_session.query(Alert).filter(Alert.category == "system").all()
    assert len(alerts) == 2


def test_independent_cadences_have_independent_counters(db_session):
    tracker = CadenceFailureTracker()
    for _ in range(CONSECUTIVE_FAILURE_ALERT_THRESHOLD - 1):
        tracker.record_failure(db_session, "news", "flaky")
    tracker.record_failure(db_session, "research", "different problem")

    assert tracker._consecutive_failures["news"] == CONSECUTIVE_FAILURE_ALERT_THRESHOLD - 1
    assert tracker._consecutive_failures["research"] == 1
    assert db_session.query(Alert).filter(Alert.category == "system").count() == 0
